# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.core.config import AppConfig, WorkflowCredentials
from cua_agent_kit.core.run_context import RunContext


@pytest.fixture
def context(tmp_path: Path) -> RunContext:
    config = AppConfig(
        playwright_headless=True,
        max_turns=40,
        workflow_credentials=WorkflowCredentials("private-user", "private-password"),
        artifacts_dir=tmp_path,
        deterministic_artifacts_dir=tmp_path / "deterministic",
        workflow_prompt="Sign in as private-user with private-password.",
        start_url="http://localhost:8081",
        database_backend="postgres",
        database_jdbc_uri="jdbc:postgresql://localhost/test",
        database_user="test",
    )
    artifacts = RunArtifacts(
        run_dir=tmp_path / "run",
        sensitive_values=("private-user", "private-password"),
    )
    return RunContext(
        config=config,
        artifacts=artifacts,
        run_id="test-run",
        execution_mode="discovery",
        prompt=artifacts.redact(config.workflow_prompt),
        prompt_sha256="test-hash",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
        status="completed",
    )
