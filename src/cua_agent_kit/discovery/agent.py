# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging

from agents import Agent, ComputerTool, ModelSettings, RunConfig, Runner
from agents.tool import ComputerToolSafetyCheckData
from openai.types.shared.reasoning import Reasoning

from cua_agent_kit.core.run_context import RunContext
from cua_agent_kit.discovery.computer import PlaywrightComputer
from cua_agent_kit.discovery.stream_output import log_streamed_events, redact

logger = logging.getLogger(__name__)


class BrowserAgent:
    def __init__(self, context: RunContext) -> None:
        self.context = context
        config = context.config
        self.config = config
        self.artifacts = context.artifacts
        self.computer = PlaywrightComputer(
            start_url=config.start_url,
            headless=config.playwright_headless,
            artifacts=self.artifacts,
        )
        self.agent = Agent(
            name="Browser workflow agent",
            instructions=("Follow the workflow prompt using the computer tool."),
            model="gpt-6-sol",
            model_settings=ModelSettings(
                tool_choice="required",
                parallel_tool_calls=False,
                reasoning=Reasoning(summary="auto"),
                store=False,
                response_include=["reasoning.encrypted_content"],
            ),
            tools=[
                ComputerTool(
                    computer=self.computer,
                    on_safety_check=self._acknowledge_safety_check,
                ),
            ],
        )

    async def run(self) -> str:
        self.context.status = "running"
        try:
            await self.computer.open()
            logger.info("Browser opened; starting discovery run")
            result = Runner.run_streamed(
                self.agent,
                self.config.workflow_prompt,
                max_turns=self.config.max_turns,
                run_config=RunConfig(tracing_disabled=True),
            )
            await log_streamed_events(
                result,
                sensitive_values=(
                    self.config.workflow_credentials.username,
                    self.config.workflow_credentials.password,
                ),
            )
            self.context.status = "completed"
            logger.info("Discovery run completed")
            return str(result.final_output)
        except BaseException:
            self.context.status = "failed"
            raise
        finally:
            try:
                if self.computer.is_open:
                    await self.computer.finish_artifacts(self.context.status)
            except Exception as exception:
                logger.warning(
                    "Artifact finalization failed: %s", type(exception).__name__
                )
            finally:
                try:
                    await self.computer.close()
                except Exception as exception:
                    logger.warning(
                        "Browser cleanup failed: %s", type(exception).__name__
                    )

    async def _acknowledge_safety_check(
        self, data: ComputerToolSafetyCheckData
    ) -> bool:
        code = data.safety_check.code or "unknown"
        message = data.safety_check.message or "No message provided."
        sensitive_values = (
            self.config.workflow_credentials.username,
            self.config.workflow_credentials.password,
        )
        logger.debug("Safety check %s: %s", code, redact(message, sensitive_values))
        return False
