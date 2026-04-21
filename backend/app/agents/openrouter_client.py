from __future__ import annotations

import json
import os
import time
from typing import Any, Optional, Type, TypeVar

from openai import OpenAI, APIStatusError
from pydantic import BaseModel, ValidationError

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
    temperature: float = 0.0
) -> AgentResult[T]:
    client = get_client()
    start_time = time.time()

    schema = schema_class.model_json_schema()
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

            usage = response.usage
            if usage:
                total_input_tokens += usage.prompt_tokens or 0
                total_output_tokens += usage.completion_tokens or 0

            choice = response.choices[0] if response.choices else None
            tool_calls = (choice.message.tool_calls or []) if choice else []
            tool_call = next((tc for tc in tool_calls if tc.function.name == TOOL_NAME), None)

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
                    return AgentResult(status="error", error=to_error_payload(error))
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
                    return AgentResult(status="error", error=to_error_payload(error))

                last_output = json.dumps(tool_input, indent=2)

            # Validate with Pydantic
            try:
                validated_data = schema_class(**tool_input)
                latency_ms = int((time.time() - start_time) * 1000)
                return AgentResult(
                    status="success",
                    data=validated_data,
                    token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens),
                    latency_ms=latency_ms,
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
                return AgentResult(status="error", error=to_error_payload(error))

        except Exception as e:
            error_type, should_retry = _classify_api_error(e)
            error = AgentError(
                config.name,
                error_type,
                f"API call failed: {str(e)}",
                attempt,
            )
            if should_retry and attempt < MAX_RETRIES:
                continue
            return AgentResult(status="error", error=to_error_payload(error))

    error = AgentError(config.name, "unknown", "Max retries exceeded", MAX_RETRIES)
    return AgentResult(status="error", error=to_error_payload(error))
