from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.agents.registry import AgentConfig
from app.agents.schemas import AgentErrorPayload, AgentResult, TokenUsage

T = TypeVar('T', bound=BaseModel)

TOOL_NAME = "structured_output"
MAX_RETRIES = 2


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


def get_client() -> anthropic.Anthropic:
    import os
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)


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

    # Create tool from Pydantic schema
    schema = schema_class.model_json_schema()
    structured_output_tool = {
        "name": TOOL_NAME,
        "description": "Submit the structured analysis output. You MUST call this tool with your complete analysis.",
        "input_schema": schema
    }

    current_user_message = user_message
    total_input_tokens = 0
    total_output_tokens = 0
    last_output = None
    last_validation_errors = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=temperature,
                system=system_prompt,
                tools=[structured_output_tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": current_user_message}]
            )

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            # Find tool use block
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use" and block.name == TOOL_NAME:
                    tool_use_block = block
                    break

            if not tool_use_block:
                error = AgentError(
                    config.name,
                    "validation",
                    "Claude did not produce a tool_use block with structured output",
                    attempt
                )
                if attempt < MAX_RETRIES:
                    current_user_message = create_retry_prompt(
                        last_output or "No output",
                        "No tool use block found"
                    )
                    continue
                return AgentResult(status="error", error=to_error_payload(error))

            # Parse the tool input
            tool_input = tool_use_block.input
            last_output = json.dumps(tool_input, indent=2)

            # Validate with Pydantic
            try:
                validated_data = schema_class(**tool_input)
                latency_ms = int((time.time() - start_time) * 1000)
                return AgentResult(
                    status="success",
                    data=validated_data,
                    token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens),
                    latency_ms=latency_ms
                )
            except ValidationError as e:
                last_validation_errors = str(e)
                if attempt < MAX_RETRIES:
                    current_user_message = create_retry_prompt(last_output, last_validation_errors)
                    continue
                error = AgentError(
                    config.name,
                    "validation",
                    f"Schema validation failed: {last_validation_errors}",
                    attempt
                )
                return AgentResult(status="error", error=to_error_payload(error))

        except Exception as e:
            error = AgentError(
                config.name,
                "api",
                f"API call failed: {str(e)}",
                attempt
            )
            if attempt < MAX_RETRIES:
                continue
            return AgentResult(status="error", error=to_error_payload(error))

    # Should not reach here
    error = AgentError(config.name, "unknown", "Max retries exceeded", MAX_RETRIES)
    return AgentResult(status="error", error=to_error_payload(error))
