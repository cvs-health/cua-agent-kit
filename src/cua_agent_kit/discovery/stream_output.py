# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging

from agents import (
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    RunResultStreaming,
    ToolCallItem,
)
from openai.types.responses import (
    ResponseComputerToolCall,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningSummaryTextDoneEvent,
    ResponseTextDeltaEvent,
)
from openai.types.responses.computer_action import ComputerAction
from openai.types.responses.response_computer_tool_call import Action

logger = logging.getLogger(__name__)


def redact(text: str, sensitive_values: tuple[str, ...]) -> str:
    for value in sensitive_values:
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def _summarize_action(
    action: Action | ComputerAction, sensitive_values: tuple[str, ...]
) -> str:
    match action.type:
        case "click":
            return f"click {action.button} ({action.x}, {action.y})"
        case "double_click" | "move":
            return f"{action.type} ({action.x}, {action.y})"
        case "scroll":
            return (
                f"scroll ({action.x}, {action.y}) "
                f"by ({action.scroll_x}, {action.scroll_y})"
            )
        case "type":
            return f"type {redact(action.text, sensitive_values)!r}"
        case "keypress":
            return f"keypress {action.keys}"
        case _:
            return action.type


def _summarize_tool_call(item: ToolCallItem, sensitive_values: tuple[str, ...]) -> str:
    match item.raw_item:
        case ResponseComputerToolCall(action=action) if action is not None:
            return _summarize_action(action, sensitive_values)
        case ResponseComputerToolCall(actions=actions) if actions:
            return ", ".join(
                _summarize_action(action, sensitive_values) for action in actions
            )
        case ResponseComputerToolCall():
            return "computer call"
        case _:
            return item.tool_name or "tool call"


def _flush_buffer(
    parts: list[str],
    sensitive_values: tuple[str, ...],
    *,
    prefix: str = "",
) -> bool:
    """Log and clear buffered text, returning whether anything was emitted."""
    if not parts:
        return False
    text = redact("".join(parts), sensitive_values)
    logger.debug("%s%s", prefix, text)
    parts.clear()
    return True


async def log_streamed_events(
    result: RunResultStreaming,
    *,
    sensitive_values: tuple[str, ...] = (),
) -> None:
    reasoning_parts: list[str] = []
    text_parts: list[str] = []
    emitted_text = False

    async for event in result.stream_events():
        match event:
            case RawResponsesStreamEvent(
                data=ResponseReasoningSummaryTextDeltaEvent(delta=delta)
            ):
                emitted_text |= _flush_buffer(text_parts, sensitive_values)
                reasoning_parts.append(delta)
            case RawResponsesStreamEvent(data=ResponseReasoningSummaryTextDoneEvent()):
                _flush_buffer(reasoning_parts, sensitive_values, prefix="[reasoning] ")
            case RawResponsesStreamEvent(data=ResponseTextDeltaEvent(delta=delta)):
                _flush_buffer(reasoning_parts, sensitive_values, prefix="[reasoning] ")
                text_parts.append(delta)
            case RunItemStreamEvent():
                _flush_buffer(reasoning_parts, sensitive_values, prefix="[reasoning] ")
                emitted_text |= _flush_buffer(text_parts, sensitive_values)
                match event:
                    case RunItemStreamEvent(
                        name="tool_called", item=ToolCallItem() as item
                    ):
                        summary = _summarize_tool_call(item, sensitive_values)
                        logger.debug("Tool call: %s", summary)
                    case RunItemStreamEvent(name="tool_output"):
                        logger.debug("Tool completed")

    _flush_buffer(reasoning_parts, sensitive_values, prefix="[reasoning] ")
    emitted_text |= _flush_buffer(text_parts, sensitive_values)
    if not emitted_text and result.final_output:
        logger.debug("%s", redact(str(result.final_output), sensitive_values))
