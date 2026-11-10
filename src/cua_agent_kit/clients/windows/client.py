# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import base64
import json
import logging
from importlib.resources import files
from io import BytesIO
from pathlib import PureWindowsPath
from typing import Any

from computer.interface.generic import GenericComputerInterface
from computer.interface.models import CommandResult
from computer.interface.windows import WindowsComputerInterface
from mslex import quote
from PIL import Image

logger = logging.getLogger(__name__)


class CheckedWindowsInterface(WindowsComputerInterface):
    """Use the pinned CUA transport, but surface errors and never replay input.

    CUA 0.5.18 input methods otherwise discard success=False responses and
    can retry ambiguous requests via WebSocket. REST works on the tested host.
    """

    async def _send_command(
        self, command: str, params: dict | None = None
    ) -> dict[str, Any]:
        async with asyncio.timeout(15):
            result = await self._send_command_rest(command, params)
        if result.get("success") is not True:
            raise RuntimeError(
                f"Windows {command} failed: {result.get('error', 'unknown')}"
            )
        return result

    async def version(self) -> dict[str, Any]:
        return await self._send_command("version")

    async def run_command(self, command: str) -> CommandResult:
        result = await self._send_command(
            "run_command", {"command": command, "timeout": 12}
        )
        return CommandResult(
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            returncode=result.get("return_code", 0),
        )


class WindowsClient:
    """Connect to an existing CUA server; never provision or stop the VM."""

    def __init__(self, *, host: str, port: int = 8000) -> None:
        self._interface = CheckedWindowsInterface(
            ip_address=host,
            api_port=port,
        )
        self._interface.delay = 0.15
        self.server_version: str | None = None
        self.dimensions: tuple[int, int] | None = None
        self.is_open = False
        self.inspection_info: dict[str, Any] = {"available": False}
        self._inspection_path: str | None = None
        self._keyboard_path: str | None = None

    @property
    def interface(self) -> GenericComputerInterface:
        if not self.is_open:
            raise RuntimeError("Windows client is not open. Call open() first.")
        return self._interface

    async def open(self) -> None:
        if self.is_open:
            return
        try:
            version = await self._interface.version()
            self.server_version = version.get("package")
            size = await self._interface.get_screen_size()
            self.dimensions = (size["width"], size["height"])
            self.is_open = True
            # Readiness requires a usable observation, not just an HTTP health result.
            await self.screenshot()
            await self._prepare_inspection()
        except BaseException:
            await self.close()
            raise

    async def screenshot(self) -> bytes:
        png = await self.interface.screenshot()
        with Image.open(BytesIO(png)) as image:
            image.verify()
            if image.format != "PNG" or image.size != self.dimensions:
                raise RuntimeError(
                    "Windows screenshot format/geometry does not match the desktop. "
                    "Reconnect after changing resolution or scaling."
                )
        return png

    async def close(self) -> None:
        # The CUA REST transport scopes and closes its HTTP session per request.
        self.is_open = False
        self.dimensions = None
        self._inspection_path = None
        self._keyboard_path = None

    async def _prepare_inspection(self) -> None:
        try:
            bootstrap = (
                "import os,json; "
                "print(json.dumps(os.path.join(os.environ['LOCALAPPDATA'], "
                "'cua-agent-kit', 'inspection')))"
            )
            command = f"python -c {quote(bootstrap)}"
            result = await self.interface.run_command(command)
            if result.returncode != 0:
                raise RuntimeError("Windows inspection directory lookup failed")
            directory = json.loads(result.stdout)
            self._inspection_path = str(
                PureWindowsPath(directory) / "inspection_probe.py"
            )
            await self.interface.create_dir(directory)
            source = files("cua_agent_kit.clients.windows").joinpath(
                "inspection_probe.py"
            )
            await self.interface.write_bytes(self._inspection_path, source.read_bytes())
            self._keyboard_path = str(PureWindowsPath(directory) / "keyboard_input.py")
            keyboard_source = files("cua_agent_kit.clients.windows").joinpath(
                "keyboard_input.py"
            )
            await self.interface.write_bytes(
                self._keyboard_path, keyboard_source.read_bytes()
            )
            self.inspection_info = await self._probe({"capture": "capabilities"})
            if not self.inspection_info.get("available"):
                logger.warning(
                    "Native inspection unavailable: run "
                    "windows-host/install.ps1 "
                    "in the Windows user session. Visual discovery can still run."
                )
        except Exception as error:
            self.inspection_info = {
                "available": False,
                "error_type": type(error).__name__,
            }
            logger.warning("Windows inspection setup failed: %s", type(error).__name__)

    async def _probe(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._inspection_path is None:
            raise RuntimeError("Windows inspection probe is not initialized")
        encoded = base64.b64encode(json.dumps(request).encode()).decode("ascii")
        result = await self.interface.run_command(
            f"python {quote(self._inspection_path)} {encoded}"
        )
        if result.returncode != 0:
            raise RuntimeError("Windows inspection probe failed")
        response = json.loads(result.stdout)
        if not isinstance(response, dict):
            raise ValueError("Windows inspection probe returned invalid metadata")
        return response

    async def inspect_target(
        self, *, point: tuple[int, int] | None = None, include_tree: bool = False
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "capture": "point" if point is not None else "focus",
            "include_tree": include_tree,
        }
        if point is not None:
            request.update(x=point[0], y=point[1])
        if not self.inspection_info.get("available"):
            return {
                "kind": "windows-controls",
                "schema_version": 1,
                "status": "unavailable",
                "capture": request["capture"],
                "errors": {
                    "setup": self.inspection_info.get(
                        "error_type", "missing_dependencies"
                    )
                },
            }
        return await self._probe(request)

    async def type_text(self, text: str) -> None:
        if self._keyboard_path is None:
            raise RuntimeError("Windows literal keyboard input is not initialized")
        # Bound command-line size and host execution time; never retry input.
        for start in range(0, len(text), 256):
            chunk = text[start : start + 256]
            encoded = base64.b64encode(json.dumps({"text": chunk}).encode()).decode(
                "ascii"
            )
            result = await self.interface.run_command(
                f"python {quote(self._keyboard_path)} {encoded}"
            )
            if result.returncode != 0:
                raise RuntimeError("Windows literal keyboard input failed")
