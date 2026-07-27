from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import HTTPException
from google import genai
from google.genai import types

from app.core.config import (
    GEMINI_AGENT_MODEL,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_DIMENSIONS,
    GEMINI_EMBEDDING_MODEL,
)


@dataclass(frozen=True)
class AgentToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentCompletion:
    text: str
    tool_calls: list[AgentToolCall]
    model_content: types.Content


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
        contents: list[types.Content],
        system_instruction: str,
        tools: list[AgentToolDefinition],
    ) -> AgentCompletion: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class GeminiAIProvider:
    def __init__(
        self,
        api_key: str | None = GEMINI_API_KEY,
        model: str = GEMINI_AGENT_MODEL,
        embedding_model: str = GEMINI_EMBEDDING_MODEL,
        embedding_dimensions: int = GEMINI_EMBEDDING_DIMENSIONS,
    ):
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        if self.embedding_dimensions != 768:
            raise ValueError(
                "GEMINI_EMBEDDING_DIMENSIONS must remain 768 until a matching "
                "vector-column migration is applied"
            )

    async def complete(
        self,
        contents: list[types.Content],
        system_instruction: str,
        tools: list[AgentToolDefinition],
    ) -> AgentCompletion:
        client = self._client()
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.parameters,
            )
            for tool in tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI provider request failed") from exc
        finally:
            await client.aio.aclose()

        if not response.candidates or not response.candidates[0].content:
            raise HTTPException(status_code=502, detail="AI provider returned no response")

        model_content = response.candidates[0].content
        text_parts: list[str] = []
        tool_calls: list[AgentToolCall] = []
        for part in model_content.parts or []:
            if part.text:
                text_parts.append(part.text)
            if part.function_call:
                tool_calls.append(
                    AgentToolCall(
                        name=part.function_call.name or "",
                        arguments=dict(part.function_call.args or {}),
                    )
                )
        return AgentCompletion(
            text="".join(text_parts).strip(),
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
        client = self._client()
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

    def _client(self) -> genai.Client:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")
        return genai.Client(api_key=self.api_key)


def text_content(role: str, text: str) -> types.Content:
    return types.Content(role=role, parts=[types.Part.from_text(text=text)])


def function_result_content(name: str, result: dict[str, Any]) -> types.Content:
    return types.Content(
        role="user",
        parts=[types.Part.from_function_response(name=name, response=result)],
    )
