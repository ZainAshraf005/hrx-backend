from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.services.ai.provider import (
    AgentToolCall,
    AgentToolDefinition,
    XkiroAIProvider,
    function_result_content,
)
from app.services.xkiro_service import XkiroService


class FakeCompletions:
    def __init__(self, response: Any):
        self.response = response
        self.request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any):
        self.request = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: Any):
        self.completions = FakeCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_xkiro_agent_completion_uses_openai_messages_and_tools():
    tool_call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(
            name="search_jobs",
            arguments='{"title":"Engineer"}',
        ),
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tool_call])
            )
        ]
    )
    client = FakeClient(response)
    provider = XkiroAIProvider(api_key="test-key")
    provider._xkiro_client = lambda: cast(Any, client)  # type: ignore[method-assign]

    completion = await provider.complete(
        contents=[{"role": "user", "content": "Find engineering jobs"}],
        system_instruction="Use HRX tools.",
        tools=[
            AgentToolDefinition(
                name="search_jobs",
                description="Search jobs",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )

    assert client.completions.request is not None
    assert client.completions.request["model"] == "mistralai/mistral-large-2512"
    assert client.completions.request["messages"][0] == {
        "role": "system",
        "content": "Use HRX tools.",
    }
    assert client.completions.request["tools"][0]["function"]["name"] == "search_jobs"
    assert completion.tool_calls == [
        AgentToolCall(
            id="call-1",
            name="search_jobs",
            arguments={"title": "Engineer"},
        )
    ]
    assert completion.model_content["tool_calls"][0]["id"] == "call-1"
    assert client.closed is True


def test_tool_result_references_xkiro_tool_call_id():
    call = AgentToolCall(id="call-1", name="search_jobs", arguments={})

    message = function_result_content(call, {"ok": True, "count": 2})

    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call-1"
    assert '"count": 2' in message["content"]


@pytest.mark.asyncio
async def test_xkiro_resume_parsing_accepts_json_fences():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='```json\n{"full_name":"Ada Lovelace","skills":["Python"]}\n```'
                )
            )
        ]
    )
    client = FakeClient(response)
    service = XkiroService(api_key="test-key")
    service._client = lambda: cast(Any, client)  # type: ignore[method-assign]

    resume = await service.extract_resume_details("Ada Lovelace uses Python.")

    assert resume.full_name == "Ada Lovelace"
    assert resume.skills == ["Python"]
    assert client.completions.request is not None
    assert client.completions.request["model"] == "mistralai/mistral-large-2512"
    assert client.closed is True
