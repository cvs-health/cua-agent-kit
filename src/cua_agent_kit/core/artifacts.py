# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import re
from pathlib import Path
from typing import Any

from cua_agent_kit.core.action import Action

ARTIFACT_SCHEMA_VERSION = 2
logger = logging.getLogger(__name__)


class RunArtifacts:
    """Persist plain evidence and metadata using the existing v2 file format."""

    def __init__(
        self,
        *,
        run_dir: Path,
        sensitive_values: tuple[str, ...] = (),
    ) -> None:
        self.run_dir = run_dir
        self.screenshots_dir = self.run_dir / "screenshots"
        self.events_path = self.run_dir / "events.jsonl"
        self._sensitive_values = sensitive_values
        self._screenshot_count = 0
        self._event_count = 0
        self._finished = False
        self._run_data: dict[str, Any] = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
        }

    def start(self, *, metadata: dict[str, Any] | None = None) -> None:
        self.screenshots_dir.mkdir(parents=True, exist_ok=False)
        self._run_data.update(metadata or {})
        logger.info("Saving run artifacts to %s", self.run_dir)

    def _save_screenshot(self, png: bytes, *, label: str) -> str | None:
        """Save supplied bytes; failed attempts still consume a sequence number."""
        try:
            self._screenshot_count += 1
            safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", label).strip("_")
            filename = f"{self._screenshot_count:04d}_{safe_label or 'screen'}.png"
            path = self.screenshots_dir / filename
            path.write_bytes(png)
            return str(path.relative_to(self.run_dir))
        except Exception as error:
            logger.warning("Screenshot write failed: %s", type(error).__name__)
            return None

    def record_action(self, action: Action) -> None:
        """Save supplied screenshot bytes and append the action that references them."""
        screenshot_path = (
            self._save_screenshot(action.screenshot, label=action.action)
            if action.screenshot is not None
            else None
        )
        try:
            self._event_count += 1
            event = {
                "sequence": self._event_count,
                "timestamp": action.timestamp.isoformat(),
                "action": action.action,
                "outcome": action.outcome,
                "url": action.url,
                "details": action.details,
                "target": action.target,
                "screenshot": screenshot_path,
            }
            with self.events_path.open("a", encoding="utf-8") as events_file:
                events_file.write(json.dumps(event, sort_keys=True) + "\n")
        except Exception as error:
            logger.warning("Event write failed: %s", type(error).__name__)

    def finish(
        self,
        *,
        final_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._finished:
            return
        self._finished = True
        self._run_data.update(metadata or {})
        self._run_data.update(
            final_url=final_url,
            screenshot_count=self._screenshot_count,
            event_count=self._event_count,
        )

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

    def redact(self, text: str) -> str:
        for value in self._sensitive_values:
            if value:
                text = text.replace(value, "[REDACTED]")
        return text
