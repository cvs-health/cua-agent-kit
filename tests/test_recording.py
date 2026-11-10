# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
from datetime import UTC, datetime
from pathlib import Path

from cua_agent_kit.core import Action, RunArtifacts


def test_recording_writes_the_artifact_contract(tmp_path: Path) -> None:
    artifacts = RunArtifacts(run_dir=tmp_path / "run")
    artifacts.start(metadata={"start_url": "https://example.test/before"})
    occurred_at = datetime(2026, 1, 1, tzinfo=UTC)
    target = {"role": "button", "accessible_name": "Continue"}
    artifacts.record_action(
        Action(
            action="click",
            timestamp=occurred_at,
            details={"x": 10},
            target=target,
            url="https://example.test/after",
            screenshot=b"supplied-png",
        )
    )
    artifacts.record_action(Action(action="verify"))
    artifacts.finish(final_url="https://example.test/after")
    artifacts.write_run_metadata({"status": "completed"})

    events = [
        json.loads(line) for line in artifacts.events_path.read_text().splitlines()
    ]
    assert events[0].pop("timestamp") == occurred_at.isoformat()
    assert events[0] == {
        "sequence": 1,
        "action": "click",
        "outcome": "success",
        "url": "https://example.test/after",
        "details": {"x": 10},
        "target": target,
        "screenshot": "screenshots/0001_click.png",
    }
    assert (artifacts.run_dir / events[0]["screenshot"]).read_bytes() == b"supplied-png"
    assert events[1]["sequence"] == 2
    assert events[1]["action"] == "verify"
    assert events[1]["screenshot"] is None
    metadata = json.loads((artifacts.run_dir / "run.json").read_text())
    assert metadata["schema_version"] == 2
    assert metadata["start_url"] == "https://example.test/before"
    assert metadata["final_url"] == "https://example.test/after"
    assert metadata["event_count"] == len(events) == 2
    assert metadata["screenshot_count"] == 1
    assert len(list(artifacts.screenshots_dir.glob("*.png"))) == 1
