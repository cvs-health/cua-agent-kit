# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import base64
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from agents import AsyncComputer, Button
from playwright.async_api import Frame, Page

from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.core.browser import BrowserSession

CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "command": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "meta": "Meta",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}

ELEMENT_METADATA_SCRIPT = r"""
(element) => {
    if (!element) return null;
    const tag = element.tagName.toLowerCase();
    const inputType = (element.getAttribute("type") || "").toLowerCase();
    const implicitRoles = {
        button: "button",
        select: "combobox",
        textarea: "textbox",
    };
    let role = element.getAttribute("role") || implicitRoles[tag] || null;
    if (!role && tag === "a" && element.hasAttribute("href")) role = "link";
    if (!role && tag === "input") {
        role = {checkbox: "checkbox", radio: "radio"}[inputType] || "textbox";
    }
    const labels = element.labels
        ? Array.from(element.labels)
              .map((label) => (label.innerText || label.textContent || "").trim())
              .filter(Boolean)
        : [];
    const text = ["input", "textarea", "select"].includes(tag)
        ? null
        : (element.innerText || element.textContent || "")
              .replace(/\s+/g, " ")
              .trim()
              .slice(0, 200) || null;
    return {
        tag,
        role,
        accessible_name:
            element.getAttribute("aria-label") ||
            labels[0] ||
            element.getAttribute("title") ||
            text,
        label: labels[0] || null,
        placeholder: element.getAttribute("placeholder"),
        test_id:
            element.getAttribute("data-testid") ||
            element.getAttribute("data-test-id"),
        id: element.id || null,
        name: element.getAttribute("name"),
        input_type: inputType || null,
        text,
    };
}
"""

ELEMENT_AT_POINT_SCRIPT = f"""
([x, y]) => ({ELEMENT_METADATA_SCRIPT})(document.elementFromPoint(x, y))
"""

ACTIVE_ELEMENT_SCRIPT = f"""
() => ({ELEMENT_METADATA_SCRIPT})(document.activeElement)
"""


class PlaywrightComputer(AsyncComputer):
    """A browser computer backed by a local Playwright Chromium process."""

    def __init__(
        self,
        *,
        start_url: str = "about:blank",
        headless: bool,
        artifacts: RunArtifacts,
        width: int = 1440,
        height: int = 900,
    ) -> None:
        self._start_url = start_url
        self._artifacts = artifacts
        self._session = BrowserSession(
            start_url=start_url,
            headless=headless,
            artifacts=artifacts,
            width=width,
            height=height,
        )

    @property
    def dimensions(self) -> tuple[int, int]:
        return self._session.dimensions

    @property
    def is_open(self) -> bool:
        return self._session.is_open

    async def open(self) -> "PlaywrightComputer":
        await self._session.open()
        return self

    async def close(self) -> None:
        await self._session.close()

    @property
    def page(self) -> Page:
        return self._session.page

    async def screenshot(self) -> str:
        png = await self.page.screenshot(full_page=False)
        await self._artifacts.record_observation(self.page, png)
        return base64.b64encode(png).decode("ascii")

    async def click(
        self,
        x: int,
        y: int,
        button: Button = "left",
        *,
        keys: list[str] | None = None,
    ) -> None:
        if button not in {"left", "middle", "right"}:
            raise ValueError(f"Unsupported Playwright mouse button: {button}")
        playwright_button: Literal["left", "middle", "right"] = button
        target = await self._target_at(x, y)

        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.page.mouse.click(x, y, button=playwright_button)

        await self._execute_action(
            "click",
            operation,
            details={"x": x, "y": y, "button": button, "keys": keys or []},
            target=target,
        )

    async def double_click(
        self,
        x: int,
        y: int,
        *,
        keys: list[str] | None = None,
    ) -> None:
        target = await self._target_at(x, y)

        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.page.mouse.dblclick(x, y)

        await self._execute_action(
            "double_click",
            operation,
            details={"x": x, "y": y, "keys": keys or []},
            target=target,
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
        target = await self._target_at(x, y)

        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.page.mouse.move(x, y)
                await self.page.mouse.wheel(scroll_x, scroll_y)

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
            target=target,
        )

    async def type(self, text: str) -> None:
        target = await self._active_target()
        await self._execute_action(
            "type",
            lambda: self.page.keyboard.type(text),
            details={"text": "[REDACTED]", "character_count": len(text)},
            target=target,
        )

    async def wait(self) -> None:
        await self._execute_action("wait", lambda: asyncio.sleep(1))

    async def move(
        self,
        x: int,
        y: int,
        *,
        keys: list[str] | None = None,
    ) -> None:
        target = await self._target_at(x, y)

        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.page.mouse.move(x, y)

        await self._execute_action(
            "move",
            operation,
            details={"x": x, "y": y, "keys": keys or []},
            target=target,
        )

    async def keypress(self, keys: list[str]) -> None:
        mapped_keys = self._normalize_keys(keys)
        target = await self._active_target()

        async def operation() -> None:
            for key in mapped_keys:
                await self.page.keyboard.down(key)
            for key in reversed(mapped_keys):
                await self.page.keyboard.up(key)

        await self._execute_action(
            "keypress",
            operation,
            details={"keys": keys},
            target=target,
        )

    async def drag(
        self,
        path: list[tuple[int, int]],
        *,
        keys: list[str] | None = None,
    ) -> None:
        if not path:
            return

        target = await self._target_at(*path[0])

        async def operation() -> None:
            async with self._hold_keys(keys):
                await self.page.mouse.move(*path[0])
                await self.page.mouse.down()
                try:
                    for point in path[1:]:
                        await self.page.mouse.move(*point)
                finally:
                    await self.page.mouse.up()

        await self._execute_action(
            "drag",
            operation,
            details={"path": path, "keys": keys or []},
            target=target,
        )

    async def finish_artifacts(self, status: str) -> None:
        await self._session.finish_artifacts(status)

    async def _execute_action(
        self,
        action: str,
        operation: Callable[[], Awaitable[None]],
        *,
        details: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
    ) -> None:
        try:
            await operation()
        except Exception as error:
            failed_details = dict(details or {})
            failed_details["error_type"] = type(error).__name__
            await self._artifacts.record_action(
                self.page,
                action=action,
                details=failed_details,
                target=target,
                outcome="error",
            )
            raise

        await self._artifacts.record_action(
            self.page,
            action=action,
            details=details,
            target=target,
        )

    async def _target_at(self, x: int, y: int) -> dict[str, Any] | None:
        for frame in reversed(self.page.frames):
            point = await self._point_in_frame(frame, x, y)
            if point is None:
                continue
            try:
                target = await frame.evaluate(ELEMENT_AT_POINT_SCRIPT, point)
            except Exception:
                continue
            if isinstance(target, dict):
                target["frame_url"] = frame.url
                target["frame_name"] = frame.name or None
                return target
        return None

    async def _active_target(self) -> dict[str, Any] | None:
        for frame in reversed(self.page.frames):
            try:
                target = await frame.evaluate(ACTIVE_ELEMENT_SCRIPT)
            except Exception:
                continue
            if not isinstance(target, dict) or target.get("tag") in {"body", "html"}:
                continue
            target["frame_url"] = frame.url
            target["frame_name"] = frame.name or None
            return target
        return None

    async def _point_in_frame(
        self,
        frame: Frame,
        x: int,
        y: int,
    ) -> list[float] | None:
        if frame == self.page.main_frame:
            return [x, y]
        try:
            frame_element = await frame.frame_element()
            box = await frame_element.bounding_box()
        except Exception:
            return None
        if box is None:
            return None
        if not (
            box["x"] <= x <= box["x"] + box["width"]
            and box["y"] <= y <= box["y"] + box["height"]
        ):
            return None
        return [x - box["x"], y - box["y"]]

    def _normalize_keys(self, keys: list[str] | None) -> list[str]:
        return [CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key) for key in keys or []]

    @asynccontextmanager
    async def _hold_keys(
        self,
        keys: list[str] | None,
    ) -> AsyncGenerator[None]:
        mapped_keys = self._normalize_keys(keys)
        try:
            for key in mapped_keys:
                await self.page.keyboard.down(key)
            yield
        finally:
            for key in reversed(mapped_keys):
                await self.page.keyboard.up(key)
