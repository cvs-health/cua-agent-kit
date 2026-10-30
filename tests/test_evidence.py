# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import logging
from typing import Literal

import pytest

from cua_agent_kit.core.run_context import RunContext, build_run_context
from cua_agent_kit.core.telemetry import emit_run_event


def test_run_context_redacts_prompt_before_hashing(context: RunContext) -> None:
    config = context.config
    context = build_run_context("discovery", config)
    assert "private-user" not in context.prompt
    assert "private-password" not in context.prompt
    assert "[REDACTED]" in context.prompt
    assert context.prompt_sha256 == hashlib.sha256(context.prompt.encode()).hexdigest()
    assert context.artifacts.run_dir.parent == config.artifacts_dir


def test_persisted_metadata_redacts_error_and_retains_run_details(
    context: RunContext,
) -> None:
    context.error = "Login failed for private-user with private-password"
    context.error_type = "RuntimeError"
    context.artifacts.write_run_metadata(context.metadata())
    text = (context.artifacts.run_dir / "run.json").read_text()
    assert "private-user" not in text
    assert "private-password" not in text
    data = json.loads(text)
    assert data["error"] == "Login failed for [REDACTED] with [REDACTED]"
    assert data["duration_seconds"] == 2.0
    assert data["status"] == "completed"
    assert data["schema_version"] == 2


@pytest.mark.parametrize("event", ["run_started", "run_finished"])
def test_run_event_logs_exclude_sensitive_data(
    context: RunContext,
    caplog: pytest.LogCaptureFixture,
    event: Literal["run_started", "run_finished"],
) -> None:
    context.error = "private-user private-password"
    context.error_type = "RuntimeError"
    with caplog.at_level(logging.INFO, logger="cua_agent_kit.events"):
        emit_run_event(context, event)
    payload = json.loads(caplog.records[-1].getMessage())
    fields = {
        "schema_version",
        "source",
        "timestamp",
        "level",
        "event",
        "run_id",
        "execution_mode",
    }
    if event == "run_finished":
        fields |= {
            "status",
            "duration_seconds",
            "error_type",
            "upload_status",
            "audit_status",
        }
        assert payload["status"] == "succeeded"
        assert payload["duration_seconds"] == 2.0
    assert set(payload) == fields
    assert "private-user" not in caplog.text
    assert "private-password" not in caplog.text
