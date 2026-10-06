import json
from dataclasses import dataclass
from typing import Any, Protocol, cast

from fastapi import HTTPException
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_DIMENSIONS,
    GEMINI_EMBEDDING_MODEL,
    XKIRO_API_KEY,
    XKIRO_BASE_URL,
    XKIRO_MODEL,
)

AgentMessage = dict[str, Any]


@dataclass(frozen=True)
class AgentToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentCompletion:
    text: str
    tool_calls: list[AgentToolCall]
    model_content: AgentMessage


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    mutation: bool = False


class AIProvider(Protocol):
    model: str

    async def complete(
        self,
        contents: list[AgentMessage],
        system_instruction: str,
        tools: list[AgentToolDefinition],
    ) -> AgentCompletion: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class XkiroAIProvider:
    """Xkiro for generation, with Gemini retained for the existing vector index."""

    def __init__(
        self,
        api_key: str | None = XKIRO_API_KEY,
        model: str = XKIRO_MODEL,
        base_url: str = XKIRO_BASE_URL,
        embedding_api_key: str | None = GEMINI_API_KEY,
        embedding_model: str = GEMINI_EMBEDDING_MODEL,
        embedding_dimensions: int = GEMINI_EMBEDDING_DIMENSIONS,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.embedding_api_key = embedding_api_key
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        if self.embedding_dimensions != 768:
            raise ValueError(
                "GEMINI_EMBEDDING_DIMENSIONS must remain 768 until a matching "
                "vector-column migration is applied"
            )

    async def complete(
        self,
        contents: list[AgentMessage],
        system_instruction: str,
        tools: list[AgentToolDefinition],
    ) -> AgentCompletion:
        client = self._xkiro_client()
        messages = cast(
            list[ChatCompletionMessageParam],
            [{"role": "system", "content": system_instruction}, *contents],
        )
        tool_definitions = cast(
            list[ChatCompletionToolParam],
            [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ],
        )
        try:
            if tool_definitions:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_definitions,
                    temperature=0,
                )
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI provider request failed") from exc
        finally:
            await client.close()

        if not response.choices:
            raise HTTPException(status_code=502, detail="AI provider returned no response")

        message = response.choices[0].message
        text = message.content or ""
        tool_calls: list[AgentToolCall] = []
        serialized_tool_calls: list[dict[str, Any]] = []
        for call in message.tool_calls or []:
            if call.type != "function":
                continue
            function_call = cast(ChatCompletionMessageFunctionToolCall, call)
            try:
                arguments = json.loads(function_call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=502,
                    detail="AI provider returned invalid tool arguments",
                ) from exc
            if not isinstance(arguments, dict):
                raise HTTPException(
                    status_code=502,
                    detail="AI provider returned invalid tool arguments",
                )
            tool_calls.append(
                AgentToolCall(
                    id=function_call.id,
                    name=function_call.function.name,
                    arguments=arguments,
                )
            )
            serialized_tool_calls.append(
                {
                    "id": function_call.id,
                    "type": "function",
                    "function": {
                        "name": function_call.function.name,
                        "arguments": function_call.function.arguments,
                    },
                }
            )

        model_content: AgentMessage = {
            "role": "assistant",
            "content": text or None,
        }
        if serialized_tool_calls:
            model_content["tool_calls"] = serialized_tool_calls
        return AgentCompletion(
            text=text.strip(),
            tool_calls=tool_calls,
            model_content=model_content,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), 32):
            embeddings.extend(
                await self._embed(
                    texts[start : start + 32],
                    task_type="RETRIEVAL_DOCUMENT",
                )
            )
        return embeddings

    async def embed_query(self, text: str) -> list[float]:
        results = await self._embed([text], task_type="RETRIEVAL_QUERY")
        return results[0]

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        client = self._gemini_embedding_client()
        try:
            response = await client.aio.models.embed_content(
                model=self.embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.embedding_dimensions,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI embedding request failed") from exc
        finally:
            await client.aio.aclose()

        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise HTTPException(status_code=502, detail="AI embedding response was incomplete")
        return [list(item.values or []) for item in embeddings]

    def _xkiro_client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="XKIRO_API_KEY is not configured")
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _gemini_embedding_client(self) -> genai.Client:
        if not self.embedding_api_key:
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY is not configured for embeddings",
            )
        return genai.Client(api_key=self.embedding_api_key)


def text_content(role: str, text: str) -> AgentMessage:
    return {
        "role": "assistant" if role == "model" else role,
        "content": text,
    }


def function_result_content(
    call: AgentToolCall,
    result: dict[str, Any],
) -> AgentMessage:
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "content": json.dumps(result, default=str),
    }
