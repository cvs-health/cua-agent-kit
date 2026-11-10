# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest
from PIL import Image

from cua_agent_kit.clients.windows.client import CheckedWindowsInterface, WindowsClient
from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.discovery.windows_computer import WindowsComputer


@pytest.fixture
def computer(tmp_path: Path) -> WindowsComputer:
    artifacts = RunArtifacts(run_dir=tmp_path / "run")
    artifacts.start()
    client = Mock(spec=WindowsClient)
    client.interface = Mock(
        key_down=AsyncMock(),
        key_up=AsyncMock(),
        mouse_down=AsyncMock(),
        mouse_up=AsyncMock(),
        move_cursor=AsyncMock(),
        scroll=AsyncMock(),
        type_text=AsyncMock(),
    )
    client.screenshot = AsyncMock(return_value=b"same screenshot bytes")
    client.type_text = AsyncMock()
    client.inspect_target = AsyncMock(
        return_value={"kind": "windows-controls", "status": "ok"}
    )
    return WindowsComputer(artifacts=artifacts, client=client)


@pytest.mark.asyncio
async def test_sdk_screenshot_and_artifact_use_identical_bytes(
    computer: WindowsComputer,
):
    encoded = await computer.screenshot()
    event = json.loads(computer.artifacts.events_path.read_text())
    assert (
        base64.b64decode(encoded)
        == (computer.artifacts.run_dir / event["screenshot"]).read_bytes()
    )
    cast(Mock, computer.client).screenshot.assert_awaited_once()
    assert event["url"] is None


@pytest.mark.asyncio
async def test_partial_key_failure_releases_keys_and_records_original_error(
    computer: WindowsComputer,
):
    interface = cast(Mock, computer.client.interface)
    original = RuntimeError("host rejected key")
    interface.key_down.side_effect = [None, original]
    with pytest.raises(RuntimeError) as caught:
        await computer.keypress(["Control", "ArrowDown"])
    assert caught.value is original
    assert interface.key_up.await_args_list == [
        call("down", delay=0),
        call("ctrl", delay=0),
    ]
    event = json.loads(computer.artifacts.events_path.read_text())
    assert event["outcome"] == "error"
    assert event["details"]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_typing_normalizes_newlines_and_does_not_log_text(
    computer: WindowsComputer,
):
    await computer.type("ABC!\r\nsecond\rthird")
    cast(Mock, computer.client).type_text.assert_awaited_once_with(
        "ABC!\nsecond\nthird"
    )
    event = json.loads(computer.artifacts.events_path.read_text())
    assert event["details"]["text"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_scroll_converts_sdk_pixels_to_host_wheel_ticks(
    computer: WindowsComputer,
):
    await computer.scroll(40, 50, 120, 600)
    interface = cast(Mock, computer.client.interface)
    interface.move_cursor.assert_awaited_once_with(40, 50, delay=0)
    interface.scroll.assert_awaited_once_with(1, -5)


@pytest.mark.asyncio
async def test_host_failure_is_not_silently_accepted_or_replayed():
    interface = CheckedWindowsInterface("unused")
    interface._send_command_rest = AsyncMock(
        return_value={"success": False, "error": "Windows desktop is locked"}
    )
    with pytest.raises(RuntimeError, match="desktop is locked"):
        await interface.type_text("hello")
    interface._send_command_rest.assert_awaited_once_with(
        "type_text", {"text": "hello"}
    )


@pytest.mark.asyncio
async def test_client_rejects_screenshot_coordinate_mismatch():
    client = WindowsClient(host="unused")
    image_bytes = BytesIO()
    Image.new("RGB", (20, 10)).save(image_bytes, format="PNG")
    client._interface.screenshot = AsyncMock(return_value=image_bytes.getvalue())
    client.is_open = True
    client.dimensions = (40, 20)
    with pytest.raises(RuntimeError, match="geometry"):
        await client.screenshot()


@pytest.mark.asyncio
async def test_click_records_pre_action_point_target(computer: WindowsComputer):
    client = cast(Mock, computer.client)
    target = {"kind": "windows-controls", "control": {"automation_id": "15"}}
    client.inspect_target.return_value = target
    timeline = Mock()
    timeline.attach_mock(client.inspect_target, "inspect")
    timeline.attach_mock(client.interface.mouse_down, "down")
    timeline.attach_mock(client.interface.mouse_up, "up")
    timeline.attach_mock(client.screenshot, "screenshot")
    await computer.click(100, 200)
    assert timeline.mock_calls == [
        call.inspect(point=(100, 200), include_tree=False),
        call.down(100, 200, button="left"),
        call.up(button="left"),
        call.screenshot(),
    ]
    event = json.loads(computer.artifacts.events_path.read_text())
    assert event["target"] == target


@pytest.mark.asyncio
async def test_inspection_failure_is_explicit_without_changing_input_outcome(
    computer: WindowsComputer,
):
    client = cast(Mock, computer.client)
    client.inspect_target.side_effect = TimeoutError("probe timed out")
    await computer.type("hello")
    client.type_text.assert_awaited_once_with("hello")
    event = json.loads(computer.artifacts.events_path.read_text())
    assert event["outcome"] == "success"
    assert event["target"]["status"] == "unavailable"
    assert event["target"]["errors"] == {"inspection": "TimeoutError"}


@pytest.mark.asyncio
async def test_typing_records_focused_control_before_input(computer: WindowsComputer):
    client = cast(Mock, computer.client)
    timeline = Mock()
    timeline.attach_mock(client.inspect_target, "inspect")
    timeline.attach_mock(client.type_text, "type")
    timeline.attach_mock(client.screenshot, "screenshot")
    await computer.type("hello")
    assert timeline.mock_calls == [
        call.inspect(point=None, include_tree=False),
        call.type("hello"),
        call.screenshot(),
    ]
