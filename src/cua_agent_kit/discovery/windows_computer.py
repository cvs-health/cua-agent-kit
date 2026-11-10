# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import base64
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, Literal

from agents import AsyncComputer, Button

from cua_agent_kit.clients.windows.client import WindowsClient
from cua_agent_kit.core.action import Action
from cua_agent_kit.core.artifacts import RunArtifacts

logger = logging.getLogger(__name__)

KEY_ALIASES = {
    "control": "ctrl",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "arrowup": "up",
    "return": "enter",
    "escape": "esc",
    "option": "alt",
    "cmd": "win",
    "command": "win",
    "meta": "win",
    "super": "win",
    "del": "delete",
}


def normalize_key(key: str) -> str:
    key = key.strip().lower()
    return KEY_ALIASES.get(key, key)


class WindowsComputer(AsyncComputer):
    """SDK computer adapter for remote Windows input and action recording."""

    def __init__(
        self,
        *,
        artifacts: RunArtifacts,
        client: WindowsClient,
    ) -> None:
        self.artifacts = artifacts
        self.client = client

    @property
    def environment(self) -> Literal["windows"]:
        return "windows"

    @property
    def dimensions(self) -> tuple[int, int] | None:
        return self.client.dimensions

    @property
    def is_open(self) -> bool:
        return self.client.is_open

    async def open(self) -> "WindowsComputer":
        await self.client.open()
        self.artifacts.start(
            metadata={
                "desktop_dimensions": self.dimensions,
                "computer_server_version": self.client.server_version,
                "windows_inspection": self.client.inspection_info,
            }
        )
        return self

    async def close(self) -> None:
        await self.client.close()

    async def finish_artifacts(self, status: str) -> None:
        self.artifacts.finish()

    async def screenshot(self) -> str:
        target = await self._inspect(include_tree=True)
        png = await self.client.screenshot()
        self.artifacts.record_action(
            Action(action="screenshot", target=target, screenshot=png)
        )
        return base64.b64encode(png).decode("ascii")

    async def click(
        self,
        x: int,
        y: int,
        button: Button = "left",
        *,
        keys: list[str] | None = None,
    ) -> None:
        async def operation() -> None:
            if button not in {"left", "right", "wheel"}:
                raise ValueError(f"Unsupported Windows mouse button: {button}")
            async with self._hold_keys(keys):
                host_button = "middle" if button == "wheel" else button
                try:
                    await self.client.interface.mouse_down(x, y, button=host_button)
                finally:
                    await self.client.interface.mouse_up(button=host_button)

        await self._execute_action(
            "click",
            operation,
            details={"x": x, "y": y, "button": button, "keys": keys or []},
            point=(x, y),
        )

    async def double_click(
        self, x: int, y: int, *, keys: list[str] | None = None
    ) -> None:
        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.client.interface.double_click(x=x, y=y)

        await self._execute_action(
            "double_click",
            operation,
            details={"x": x, "y": y, "keys": keys or []},
            point=(x, y),
        )

    async def scroll(
        self,
        x: int,
        y: int,
        scroll_x: int,
        scroll_y: int,
        *,
        keys: list[str] | None = None,
    ) -> None:
        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.client.interface.move_cursor(x, y, delay=0)
                # SDK deltas are pixels (positive = down/right); pynput uses
                # wheel ticks (positive = up/right). Use 120 pixels per tick.
                dx = self._wheel_ticks(scroll_x)
                dy = -self._wheel_ticks(scroll_y)
                await self.client.interface.scroll(dx, dy)

        await self._execute_action(
            "scroll",
            operation,
            details={
                "x": x,
                "y": y,
                "scroll_x": scroll_x,
                "scroll_y": scroll_y,
                "keys": keys or [],
            },
            point=(x, y),
        )

    @staticmethod
    def _wheel_ticks(delta: int) -> int:
        if delta == 0:
            return 0
        return (1 if delta > 0 else -1) * max(1, round(abs(delta) / 120))

    async def type(self, text: str) -> None:
        # pynput treats CR and LF separately; keep one Enter per logical newline.
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        await self._execute_action(
            "type",
            lambda: self.client.type_text(normalized),
            details={
                "text": "[REDACTED]",
                "character_count": len(text),
                "input_method": "virtual_keys",
            },
        )

    async def wait(self) -> None:
        await self._execute_action("wait", lambda: asyncio.sleep(1), include_tree=True)

    async def move(self, x: int, y: int, *, keys: list[str] | None = None) -> None:
        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.client.interface.move_cursor(x, y)

        await self._execute_action(
            "move",
            operation,
            details={"x": x, "y": y, "keys": keys or []},
            point=(x, y),
        )

    async def keypress(self, keys: list[str]) -> None:
        async def operation() -> None:
            async with self._hold_keys(keys):
                pass

        await self._execute_action("keypress", operation, details={"keys": keys})

    async def drag(
        self, path: list[tuple[int, int]], *, keys: list[str] | None = None
    ) -> None:
        if not path:
            return

        async def operation() -> None:
            async with self._hold_keys(keys):
                try:
                    await self.client.interface.mouse_down(*path[0], button="left")
                    for x, y in path[1:]:
                        await self.client.interface.move_cursor(x, y)
                finally:
                    await self.client.interface.mouse_up(button="left")

        await self._execute_action(
            "drag",
            operation,
            details={"path": path, "keys": keys or []},
            point=path[0],
        )

    @asynccontextmanager
    async def _hold_keys(self, keys: list[str] | None) -> AsyncGenerator[None]:
        held: list[str] = []
        operation_failed = False
        try:
            for key in keys or []:
                normalized = normalize_key(key)
                # Attempt cleanup even if acknowledgement of key_down fails.
                held.append(normalized)
                await self.client.interface.key_down(normalized, delay=0)
            yield
        except BaseException:
            operation_failed = True
            raise
        finally:
            release_error: Exception | None = None
            for key in reversed(held):
                try:
                    await self.client.interface.key_up(key, delay=0)
                except Exception as error:
                    release_error = error
                    logger.warning("Windows key release failed: %s", key)
            if release_error is not None and not operation_failed:
                raise release_error

    async def _capture(self) -> bytes | None:
        try:
            return await self.client.screenshot()
        except Exception as error:
            logger.warning(
                "Windows screenshot capture failed: %s", type(error).__name__
            )
            return None

    async def _inspect(
        self, *, point: tuple[int, int] | None = None, include_tree: bool = False
    ) -> dict[str, Any]:
        try:
            return await self.client.inspect_target(
                point=point, include_tree=include_tree
            )
        except Exception as error:
            logger.warning(
                "Windows control inspection failed: %s", type(error).__name__
            )
            return {
                "kind": "windows-controls",
                "schema_version": 1,
                "capture": "point" if point is not None else "focus",
                "status": "unavailable",
                "errors": {"inspection": type(error).__name__},
            }

    async def _execute_action(
        self,
        action: str,
        operation: Callable[[], Awaitable[None]],
        *,
        details: dict[str, Any] | None = None,
        point: tuple[int, int] | None = None,
        include_tree: bool = False,
    ) -> None:
        target = await self._inspect(point=point, include_tree=include_tree)
        try:
            await operation()
        except Exception as error:
            performed = Action(
                action=action,
                outcome="error",
                details={**(details or {}), "error_type": type(error).__name__},
                target=target,
            )
            self.artifacts.record_action(
                replace(performed, screenshot=await self._capture())
            )
            raise
        performed = Action(action=action, details=details or {}, target=target)
        self.artifacts.record_action(
            replace(performed, screenshot=await self._capture())
        )
