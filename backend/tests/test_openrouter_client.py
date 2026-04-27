from __future__ import annotations

import json
from types import SimpleNamespace

from pydantic import BaseModel

from app.agents.openrouter_client import TOOL_NAME, call_agent
from app.agents.registry import AgentConfig, PipelinePhase


class _SampleSchema(BaseModel):
    summary: str


class _ContainerSchema(BaseModel):
    summary: str
    items: list[str]
    details: dict[str, str]


def _config() -> AgentConfig:
    return AgentConfig(
        name="test-agent",
        prompt_key="TEST_PROMPT",
        schema_class=_SampleSchema,
        model="z-ai/glm-5.1",
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=[],
        max_tokens=256,
    )


def test_openrouter_client_sets_provider_response_flags_on_success(monkeypatch) -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=TOOL_NAME,
                                arguments=json.dumps({"summary": "ok"}),
                            )
                        )
                    ],
                )
            )
        ],
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: response)
        )
    )
    monkeypatch.setattr("app.agents.openrouter_client.get_client", lambda: client)
    diagnostic_context = {"capture_prompt_bodies": True}

    result = call_agent(
        _config(),
        "SYSTEM BODY",
        "## Test Context\n{\"metrics\":{\"revenue\":100}}",
        _SampleSchema,
        diagnostic_context=diagnostic_context,
    )

    assert result.status == "success"
    assert result.token_usage.input == 11
    assert result.token_usage.output == 7
    assert result.diagnostics["provider_response_received"] is True
    assert result.diagnostics["usage_received"] is True
    assert result.diagnostics["tool_call_found"] is True
    assert result.diagnostics["validation_passed"] is True
    assert result.diagnostics["token_usage_known"] is True
    assert result.diagnostics["system_prompt"] == "SYSTEM BODY"
    assert result.diagnostics["user_message"].startswith("## Test Context")
    assert result.diagnostics["schema_chars"] > 0
    assert result.diagnostics["request_started_at"] is not None
    assert result.diagnostics["request_finished_at"] is not None


def test_openrouter_client_coerces_stringified_json_containers(monkeypatch) -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=TOOL_NAME,
                                arguments=json.dumps(
                                    {
                                        "summary": "ok",
                                        "items": "[]",
                                        "details": "{\"source\":\"agent\"}",
                                    }
                                ),
                            )
                        )
                    ],
                )
            )
        ],
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: response)
        )
    )
    monkeypatch.setattr("app.agents.openrouter_client.get_client", lambda: client)

    result = call_agent(
        _config(),
        "SYSTEM BODY",
        "## Test Context\n{}",
        _ContainerSchema,
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data.items == []
    assert result.data.details == {"source": "agent"}
    assert result.diagnostics["validation_passed"] is True


def test_openrouter_client_timeout_path_preserves_prompt_diagnostics(monkeypatch) -> None:
    def raise_timeout(**_kwargs):
        raise TimeoutError("provider timed out")

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=raise_timeout)
        )
    )
    monkeypatch.setattr("app.agents.openrouter_client.get_client", lambda: client)

    result = call_agent(
        _config(),
        "SYSTEM BODY",
        "## Test Context\n{\"metrics\":{\"revenue\":100}}",
        _SampleSchema,
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.diagnostics["prompt_chars"] > 0
    assert result.diagnostics["schema_chars"] > 0
    assert result.diagnostics["provider_response_received"] is False
    assert result.diagnostics["usage_received"] is False
    assert result.diagnostics["token_usage_known"] is False
    assert result.diagnostics["request_finished_at"] is not None
