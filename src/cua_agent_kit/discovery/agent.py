# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging

from agents import Agent, AsyncComputer, ComputerTool, ModelSettings, RunConfig, Runner
from agents.tool import ComputerToolSafetyCheckData
from openai.types.shared.reasoning import Reasoning

from cua_agent_kit.discovery.stream_output import log_streamed_events, redact

logger = logging.getLogger(__name__)


class ComputerAgent:
    """Run the agent loop with an injected computer."""

    def __init__(
        self,
        computer: AsyncComputer,
        *,
        model: str,
        sensitive_values: tuple[str, ...] = (),
        runner: type[Runner] = Runner,
    ) -> None:
        self.runner = runner
        self.sensitive_values = sensitive_values
        self.agent = Agent(
            name="Computer workflow agent",
            instructions=("Follow the workflow prompt using the computer tool."),
            model=model,
            model_settings=ModelSettings(
                tool_choice="required",
                parallel_tool_calls=False,
                reasoning=Reasoning(summary="auto"),
                store=False,
                response_include=["reasoning.encrypted_content"],
            ),
            tools=[
                ComputerTool(
                    computer=computer,
                    on_safety_check=self._acknowledge_safety_check,
                ),
            ],
        )

    async def run(self, *, prompt: str, max_turns: int) -> str:
        result = self.runner.run_streamed(
            self.agent,
            prompt,
            max_turns=max_turns,
            run_config=RunConfig(tracing_disabled=True),
        )
        await log_streamed_events(result, sensitive_values=self.sensitive_values)
        return str(result.final_output)

    async def _acknowledge_safety_check(
        self, data: ComputerToolSafetyCheckData
    ) -> bool:
        code = data.safety_check.code or "unknown"
        message = data.safety_check.message or "No message provided."
        logger.debug(
            "Safety check %s: %s", code, redact(message, self.sensitive_values)
        )
        return False
