# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import Mock

import pytest
from agents import AsyncComputer, ComputerTool, RunResultStreaming

from cua_agent_kit.discovery.agent import ComputerAgent


@pytest.mark.asyncio
async def test_agent_uses_injected_computer_and_runs_supplied_prompt() -> None:
    async def stream_events():
        for event in ():
            yield event

    computer = Mock(spec=AsyncComputer)
    result = Mock(spec=RunResultStreaming, final_output="finished")
    result.stream_events = stream_events
    sdk_runner = Mock(run_streamed=Mock(return_value=result))
    agent = ComputerAgent(
        computer, model="test-model", runner=sdk_runner, sensitive_values=("secret",)
    )

    assert agent.agent.model == "test-model"
    tool = agent.agent.tools[0]
    assert isinstance(tool, ComputerTool)
    assert tool.computer is computer
    assert await agent.run(prompt="Do the task", max_turns=3) == "finished"
    assert sdk_runner.run_streamed.call_args.args == (agent.agent, "Do the task")
    assert sdk_runner.run_streamed.call_args.kwargs["max_turns"] == 3
    assert (
        sdk_runner.run_streamed.call_args.kwargs["run_config"].tracing_disabled is True
    )
