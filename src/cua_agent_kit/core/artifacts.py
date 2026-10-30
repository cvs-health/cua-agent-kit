# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page

ARTIFACT_SCHEMA_VERSION = 2
logger = logging.getLogger(__name__)


class RunArtifacts:
    """Persist screenshots, semantic actions, metadata, and a Playwright trace."""

    def __init__(
        self,
        *,
        run_dir: Path,
        sensitive_values: tuple[str, ...] = (),
    ) -> None:
        self.run_dir = run_dir
        self.screenshots_dir = self.run_dir / "screenshots"
        self.events_path = self.run_dir / "events.jsonl"
        self.trace_path = self.run_dir / "trace.zip"
        self._sensitive_values = sensitive_values
        self._screenshot_count = 0
        self._event_count = 0
        self._trace_started = False
        self._finished = False
        self._run_data: dict[str, Any] = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
        }

    async def start(
        self,
        context: BrowserContext,
        page: Page,
        *,
        start_url: str,
    ) -> None:
        self.screenshots_dir.mkdir(parents=True, exist_ok=False)
        self._run_data.update(
            start_url=start_url,
            viewport=page.viewport_size,
        )
        try:
            await context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
            )
            self._trace_started = True
        except Exception as error:
            await self.record_event(
                page,
                action="trace_start",
                outcome="error",
                details={"error": self._safe_error(error)},
            )
        logger.info("Saving run artifacts to %s", self.run_dir)

    async def capture(
        self,
        page: Page,
        label: str,
        *,
        png: bytes | None = None,
    ) -> str | None:
        """Capture a screenshot without allowing capture failure to stop the run."""
        try:
            self._screenshot_count += 1
            safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", label).strip("_")
            filename = f"{self._screenshot_count:04d}_{safe_label or 'screen'}.png"
            path = self.screenshots_dir / filename
            if png is None:
                await page.screenshot(path=str(path), full_page=False)
            else:
                path.write_bytes(png)
            return str(path.relative_to(self.run_dir))
        except Exception as error:
            logger.warning("Screenshot capture failed: %s", type(error).__name__)
            return None

    async def record_action(
        self,
        page: Page,
        *,
        action: str,
        details: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> None:
        screenshot = await self.capture(page, action)
        await self.record_event(
            page,
            action=action,
            details=details,
            target=target,
            outcome=outcome,
            screenshot=screenshot,
        )

    async def record_observation(self, page: Page, png: bytes) -> None:
        screenshot = await self.capture(page, "screenshot", png=png)
        await self.record_event(
            page,
            action="screenshot",
            outcome="success",
            screenshot=screenshot,
        )

    async def record_event(
        self,
        page: Page,
        *,
        action: str,
        outcome: str,
        details: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        screenshot: str | None = None,
    ) -> None:
        try:
            self._event_count += 1
            event = {
                "sequence": self._event_count,
                "timestamp": _utc_now(),
                "action": action,
                "outcome": outcome,
                "url": page.url,
                "details": details or {},
                "target": target,
                "screenshot": screenshot,
            }
            with self.events_path.open("a", encoding="utf-8") as events_file:
                events_file.write(json.dumps(event, sort_keys=True) + "\n")
        except Exception as error:
            logger.warning("Event write failed: %s", type(error).__name__)

    async def finish(
        self,
        context: BrowserContext,
        page: Page,
        *,
        status: str,
    ) -> None:
        if self._finished:
            return
        self._finished = True

        await self.capture(page, f"final_{status}")
        trace_error: str | None = None
        if self._trace_started:
            try:
                await context.tracing.stop(path=str(self.trace_path))
            except Exception as trace_exception:
                trace_error = self._safe_error(trace_exception)

        self._run_data.update(
            final_url=page.url,
            screenshot_count=self._screenshot_count,
            event_count=self._event_count,
        )
        if trace_error:
            self._run_data["trace_error"] = trace_error

    def write_run_metadata(self, metadata: dict[str, Any]) -> None:
        run_data = {**self._run_data, **metadata}
        if run_data.get("error"):
            run_data["error"] = self.redact(run_data["error"])
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "run.json"
        path.write_text(
            json.dumps(run_data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _safe_error(self, error: BaseException) -> str:
        return self._redact(f"{type(error).__name__}: {error}")

    def redact(self, text: str) -> str:
        for value in self._sensitive_values:
            if value:
                text = text.replace(value, "[REDACTED]")
        return text

    def _redact(self, text: str) -> str:
        return self.redact(text)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
