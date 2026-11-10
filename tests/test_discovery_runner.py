# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace
from unittest.mock import AsyncMock, Mock, call

import pytest

from cua_agent_kit.core.run_context import RunContext
from cua_agent_kit.discovery.agent import ComputerAgent
from cua_agent_kit.discovery.computer import PlaywrightComputer
from cua_agent_kit.discovery.runner import execute_run
from cua_agent_kit.discovery.windows_computer import WindowsComputer


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("computer_type", [PlaywrightComputer, WindowsComputer])
async def test_runner_owns_computer_lifecycle_and_publishes_after_cleanup(
    context: RunContext, fails: bool, computer_type: type
) -> None:
    context = replace(context, status="running", finished_at=None)
    computer = Mock(spec=computer_type, is_open=True)
    computer.open = AsyncMock()
    computer.finish_artifacts = AsyncMock()
    computer.close = AsyncMock()
    agent = Mock(spec=ComputerAgent, run=AsyncMock(return_value="Done private-user"))
    original = RuntimeError("run failed")
    if fails:
        agent.run.side_effect = original
    database = Mock(create_run=AsyncMock(), finish_run=AsyncMock())
    storage = Mock(upload_run=AsyncMock())
    lifecycle = Mock()
    lifecycle.attach_mock(database.create_run, "create")
    lifecycle.attach_mock(computer.open, "open")
    lifecycle.attach_mock(agent.run, "execute")
    lifecycle.attach_mock(computer.finish_artifacts, "finalize")
    lifecycle.attach_mock(computer.close, "close")
    lifecycle.attach_mock(storage.upload_run, "upload")
    lifecycle.attach_mock(database.finish_run, "finish")

    if fails:
        with pytest.raises(RuntimeError) as caught:
            await execute_run(context, computer, agent, database, storage)
        assert caught.value is original
    else:
        await execute_run(context, computer, agent, database, storage)

    status = "failed" if fails else "completed"
    assert context.status == status
    assert context.final_output == (None if fails else "Done [REDACTED]")
    assert context.finished_at is not None
    assert lifecycle.mock_calls == [
        call.create(context),
        call.open(),
        call.execute(
            prompt=context.config.workflow_prompt, max_turns=context.config.max_turns
        ),
        call.finalize(status),
        call.close(),
        call.upload(context),
        call.finish(context),
    ]
