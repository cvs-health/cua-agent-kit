# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import logging

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from cua_agent_kit.core.action import Action
from cua_agent_kit.core.artifacts import RunArtifacts

logger = logging.getLogger(__name__)


class BrowserSession:
    """Shared Playwright lifecycle for AI-driven and deterministic workflows."""

    def __init__(
        self,
        *,
        start_url: str,
        headless: bool,
        artifacts: RunArtifacts,
        width: int = 1440,
        height: int = 900,
    ) -> None:
        self.start_url = start_url
        self.headless = headless
        self.artifacts = artifacts
        self.dimensions = (width, height)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._trace_started = False
        self._artifacts_finished = False
        self.trace_path = artifacts.run_dir / "trace.zip"

    @property
    def is_open(self) -> bool:
        return self._page is not None and self._context is not None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser session is not open. Call open() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser session is not open. Call open() first.")
        return self._context

    async def open(self) -> "BrowserSession":
        if self._playwright is not None:
            return self

        width, height = self.dimensions
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[f"--window-size={width},{height}"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": width, "height": height},
            )
            self._page = await self._context.new_page()
            self.artifacts.start(
                metadata={
                    "start_url": self.start_url,
                    "viewport": self._page.viewport_size,
                }
            )
            try:
                await self._context.tracing.start(
                    screenshots=True, snapshots=True, sources=True
                )
                self._trace_started = True
            except Exception as error:
                self.artifacts.record_action(
                    Action(
                        action="trace_start",
                        outcome="error",
                        url=self._page.url,
                        details={"error": self._safe_error(error)},
                    ),
                )
            await self._page.goto(self.start_url, wait_until="domcontentloaded")
            self.artifacts.record_action(
                Action(
                    action="navigate",
                    details={"url": self.start_url},
                    url=self.page.url,
                    screenshot=await self.screenshot(),
                )
            )
        except Exception:
            raise

        return self

    async def screenshot(self) -> bytes | None:
        """Capture a screenshot without letting capture failures stop execution."""
        try:
            return await self.page.screenshot(full_page=False)
        except Exception as error:
            logger.warning("Screenshot capture failed: %s", type(error).__name__)
            return None

    async def finish_artifacts(self, status: str) -> None:
        if self._artifacts_finished:
            return
        self._artifacts_finished = True

        final_url = self.page.url
        metadata = {}
        try:
            if self._trace_started:
                try:
                    await self.context.tracing.stop(path=str(self.trace_path))
                except Exception as error:
                    metadata["trace_error"] = self._safe_error(error)
        finally:
            # Preserve metadata even if trace shutdown is cancelled.
            self.artifacts.finish(
                final_url=final_url,
                metadata=metadata,
            )

    def _safe_error(self, error: Exception) -> str:
        return self.artifacts.redact(f"{type(error).__name__}: {error}")

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
