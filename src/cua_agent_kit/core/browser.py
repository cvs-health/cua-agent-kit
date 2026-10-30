# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from cua_agent_kit.core.artifacts import RunArtifacts


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
            await self.artifacts.start(
                self._context,
                self._page,
                start_url=self.start_url,
            )
            await self._page.goto(self.start_url, wait_until="domcontentloaded")
            await self.artifacts.record_action(
                self._page,
                action="navigate",
                details={"url": self.start_url},
            )
        except Exception:
            raise

        return self

    async def finish_artifacts(self, status: str) -> None:
        await self.artifacts.finish(
            self.context,
            self.page,
            status=status,
        )

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
