# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from cua_agent_kit.clients.object_storage.object_storage import RunStorageReference
from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.core.config import AppConfig


@dataclass
class RunContext:
    config: AppConfig
    artifacts: RunArtifacts
    run_id: str
    execution_mode: str
    prompt: str
    prompt_sha256: str
    started_at: datetime
    status: str = "running"
    finished_at: datetime | None = None
    terminal_assertion: str | None = None
    error: str | None = None
    error_type: str | None = None
    storage: RunStorageReference | None = None
    upload_error: str | None = None
    upload_status: str = "not_attempted"
    audit_status: str = "not_attempted"

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 3)

    def metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "run_id": self.run_id,
            "execution_mode": self.execution_mode,
            "prompt": self.prompt,
            "prompt_sha256": self.prompt_sha256,
            "started_at": self.started_at.isoformat(),
            "status": self.status,
        }
        if self.finished_at is not None:
            data.update(
                completed_at=self.finished_at.isoformat(),
                terminal_assertion=self.terminal_assertion,
                duration_seconds=self.duration_seconds,
                error_type=self.error_type,
            )
        if self.error:
            data["error"] = self.error
        return data


def build_run_context(execution_mode: str, config: AppConfig) -> RunContext:
    started_at = datetime.now(UTC)
    run_id = f"{started_at:%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    root = (
        config.artifacts_dir
        if execution_mode == "discovery"
        else config.deterministic_artifacts_dir
    )
    credentials = config.workflow_credentials
    artifacts = RunArtifacts(
        run_dir=root / run_id,
        sensitive_values=(credentials.username, credentials.password),
    )
    prompt = artifacts.redact(config.workflow_prompt)
    return RunContext(
        config=config,
        artifacts=artifacts,
        run_id=run_id,
        execution_mode=execution_mode,
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        started_at=started_at,
    )
