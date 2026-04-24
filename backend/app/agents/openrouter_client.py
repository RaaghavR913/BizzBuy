from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, MutableMapping, Optional, Type, TypeVar

try:
    from openai import OpenAI, APIStatusError
except ModuleNotFoundError:  # pragma: no cover - exercised in test environments without the SDK installed
    OpenAI = None

    class APIStatusError(Exception):
        status_code: int | None = None
from pydantic import BaseModel, ValidationError

from app.agents.context_builders import describe_user_message
from app.agents.registry import AgentConfig
from app.agents.schemas import AgentErrorPayload, AgentResult, TokenUsage

T = TypeVar('T', bound=BaseModel)

TOOL_NAME = "structured_output"
MAX_RETRIES = 2

# HTTP status codes that indicate a non-transient, non-retryable error.
# Retrying these wastes API credits and time.
_NON_RETRYABLE_STATUS_CODES = {
    401: "auth_error",
    402: "billing_error",
    403: "auth_error",
    404: "model_not_found",
}


def _classify_api_error(exc: Exception) -> tuple[str, bool]:
    """Return (error_type, should_retry) for an API exception."""
    if isinstance(exc, APIStatusError):
        code = exc.status_code
        if code in _NON_RETRYABLE_STATUS_CODES:
            return _NON_RETRYABLE_STATUS_CODES[code], False
        if code == 429:
            return "rate_limit", True
        if 500 <= code < 600:
            return "server_error", True
        return "api_error", False
    return "api_error", True


def to_error_payload(error: AgentError) -> AgentErrorPayload:
    return AgentErrorPayload(
        agent_name=error.agent_name,
        error_type=error.error_type,
        message=error.message,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        retry_count=error.retry_count,
    )


class AgentError(Exception):
    def __init__(self, agent_name: str, error_type: str, message: str, retry_count: int):
        self.agent_name = agent_name
        self.error_type = error_type
        self.message = message
        self.retry_count = retry_count
        super().__init__(f"{agent_name}: {message}")


def get_client() -> OpenAI:
    if OpenAI is None:
        raise ValueError("openai package is not installed")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "https://bizbuy.local"),
            "X-Title": "BizBuy Diligence Pipeline",
        },
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage_received(usage: Any) -> bool:
    return bool(
        usage
        and any(
            getattr(usage, field, None) is not None
            for field in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
    )


def _base_diagnostics(
    *,
    config: AgentConfig,
    system_prompt: str,
    user_message: str,
    schema_chars: int,
    capture_prompt_bodies: bool,
) -> dict[str, Any]:
    prompt_diagnostics = describe_user_message(user_message)
    prompt_diagnostics["system_prompt_chars"] = len(system_prompt)
    prompt_diagnostics["schema_chars"] = schema_chars
    prompt_diagnostics["prompt_chars"] = (
        prompt_diagnostics.get("prompt_chars", 0)
        + len(system_prompt)
        + schema_chars
    )
    prompt_diagnostics["model"] = config.model
    prompt_diagnostics["provider_response_received"] = False
    prompt_diagnostics["usage_received"] = False
    prompt_diagnostics["tool_call_found"] = False
    prompt_diagnostics["validation_passed"] = False
    prompt_diagnostics["token_usage_known"] = False
    prompt_diagnostics["token_usage_unknown_due_to_timeout"] = False
    prompt_diagnostics["request_started_at"] = None
    prompt_diagnostics["request_finished_at"] = None
    prompt_diagnostics["attempt_count"] = 0
    if capture_prompt_bodies:
        prompt_diagnostics["system_prompt"] = system_prompt
        prompt_diagnostics["user_message"] = user_message
    return prompt_diagnostics


def _write_diagnostics(
    base: MutableMapping[str, Any],
    target: MutableMapping[str, Any] | None,
    updates: dict[str, Any],
) -> None:
    base.update(updates)
    if target is not None:
        target.update(updates)


def _merged_diagnostics(
    base: dict[str, Any],
    diagnostic_context: MutableMapping[str, Any] | None,
    **updates: Any,
) -> dict[str, Any]:
    merged = dict(base)
    if diagnostic_context:
        merged.update(diagnostic_context)
    merged.update(updates)
    return merged


def create_retry_prompt(last_output: str, validation_errors: str) -> str:
    return f"""
Your previous response was invalid. Here are the validation errors:
{validation_errors}

Your previous output was:
{last_output}

Please fix these errors and provide a valid response matching the required schema.
""".strip()


def call_agent(
    config: AgentConfig,
    system_prompt: str,
    user_message: str,
    schema_class: Type[T],
    temperature: float = 0.0,
    *,
    diagnostic_context: MutableMapping[str, Any] | None = None,
) -> AgentResult[T]:
    client = get_client()
    start_time = time.time()

    schema = schema_class.model_json_schema()
    schema_chars = len(json.dumps(schema, separators=(",", ":"), default=str))
    capture_prompt_bodies = bool(diagnostic_context and diagnostic_context.get("capture_prompt_bodies"))
    prompt_diagnostics = _base_diagnostics(
        config=config,
        system_prompt=system_prompt,
        user_message=user_message,
        schema_chars=schema_chars,
        capture_prompt_bodies=capture_prompt_bodies,
    )
    _write_diagnostics(prompt_diagnostics, diagnostic_context, prompt_diagnostics)
    structured_output_tool = {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": "Submit the structured analysis output. You MUST call this function with your complete analysis.",
            "parameters": schema,
        },
    }

    current_user_message = user_message
    total_input_tokens = 0
    total_output_tokens = 0
    last_output: Optional[str] = None
    last_validation_errors: Optional[str] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            request_started_at = _utc_timestamp()
            _write_diagnostics(
                prompt_diagnostics,
                diagnostic_context,
                {
                    "attempt_count": attempt + 1,
                    "request_started_at": request_started_at,
                    "request_finished_at": None,
                },
            )
            response = client.chat.completions.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_user_message},
                ],
                tools=[structured_output_tool],
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            )

            request_finished_at = _utc_timestamp()
            usage = response.usage
            usage_received = _usage_received(usage)
            _write_diagnostics(
                prompt_diagnostics,
                diagnostic_context,
                {
                    "request_finished_at": request_finished_at,
                    "provider_response_received": True,
                    "usage_received": usage_received,
                    "token_usage_known": usage_received,
                },
            )
            if usage:
                total_input_tokens += usage.prompt_tokens or 0
                total_output_tokens += usage.completion_tokens or 0

            choice = response.choices[0] if response.choices else None
            tool_calls = (choice.message.tool_calls or []) if choice else []
            tool_call = next((tc for tc in tool_calls if tc.function.name == TOOL_NAME), None)
            tool_call_found = tool_call is not None
            _write_diagnostics(
                prompt_diagnostics,
                diagnostic_context,
                {
                    "tool_call_found": tool_call_found,
                },
            )

            if not tool_call:
                # Some models may return the JSON in message.content instead of tool_calls.
                # Attempt to parse content as fallback before triggering a retry.
                raw_content = (choice.message.content or "") if choice else ""
                if raw_content.strip():
                    try:
                        tool_input = json.loads(raw_content)
                        last_output = json.dumps(tool_input, indent=2)
                    except (json.JSONDecodeError, ValueError):
                        tool_input = None
                else:
                    tool_input = None

                if tool_input is None:
                    error = AgentError(
                        config.name,
                        "validation",
                        "Model did not produce a function call with structured output",
                        attempt,
                    )
                    if attempt < MAX_RETRIES:
                        current_user_message = create_retry_prompt(
                            last_output or "No output",
                            "No function call found in response",
                        )
                        continue
                    return AgentResult(
                        status="error",
                        error=to_error_payload(error),
                        diagnostics=_merged_diagnostics(
                            prompt_diagnostics,
                            diagnostic_context,
                            response_chars=len(last_output or raw_content or ""),
                        ),
                    )
            else:
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, ValueError) as parse_err:
                    error = AgentError(
                        config.name,
                        "validation",
                        f"Could not parse function arguments as JSON: {parse_err}",
                        attempt,
                    )
                    if attempt < MAX_RETRIES:
                        current_user_message = create_retry_prompt(
                            tool_call.function.arguments or "No output",
                            str(parse_err),
                        )
                        continue
                    return AgentResult(
                        status="error",
                        error=to_error_payload(error),
                        diagnostics=_merged_diagnostics(
                            prompt_diagnostics,
                            diagnostic_context,
                            response_chars=len(tool_call.function.arguments or ""),
                        ),
                    )

                last_output = json.dumps(tool_input, indent=2)

            # Validate with Pydantic
            try:
                validated_data = schema_class(**tool_input)
                latency_ms = int((time.time() - start_time) * 1000)
                _write_diagnostics(
                    prompt_diagnostics,
                    diagnostic_context,
                    {
                        "validation_passed": True,
                    },
                )
                return AgentResult(
                    status="success",
                    data=validated_data,
                    token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens),
                    latency_ms=latency_ms,
                    diagnostics=_merged_diagnostics(
                        prompt_diagnostics,
                        diagnostic_context,
                        response_chars=len(last_output or ""),
                    ),
                )
            except ValidationError as e:
                last_validation_errors = str(e)
                if attempt < MAX_RETRIES:
                    current_user_message = create_retry_prompt(
                        last_output or "No output", last_validation_errors
                    )
                    continue
                error = AgentError(
                    config.name,
                    "validation",
                    f"Schema validation failed: {last_validation_errors}",
                    attempt,
                )
                return AgentResult(
                    status="error",
                    error=to_error_payload(error),
                    diagnostics=_merged_diagnostics(
                        prompt_diagnostics,
                        diagnostic_context,
                        response_chars=len(last_output or ""),
                    ),
                )

        except Exception as e:
            _write_diagnostics(
                prompt_diagnostics,
                diagnostic_context,
                {
                    "attempt_count": attempt + 1,
                    "request_finished_at": _utc_timestamp(),
                },
            )
            error_type, should_retry = _classify_api_error(e)
            error = AgentError(
                config.name,
                error_type,
                f"API call failed: {str(e)}",
                attempt,
            )
            if should_retry and attempt < MAX_RETRIES:
                continue
            return AgentResult(
                status="error",
                error=to_error_payload(error),
                diagnostics=_merged_diagnostics(
                    prompt_diagnostics,
                    diagnostic_context,
                    response_chars=len(last_output or ""),
                ),
            )

    error = AgentError(config.name, "unknown", "Max retries exceeded", MAX_RETRIES)
    return AgentResult(
        status="error",
        error=to_error_payload(error),
        diagnostics=_merged_diagnostics(
            prompt_diagnostics,
            diagnostic_context,
            response_chars=len(last_output or ""),
        ),
    )
