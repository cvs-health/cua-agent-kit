# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from cua_agent_kit.clients.database.database import DatabaseClient, RunAuditEntry
from cua_agent_kit.clients.object_storage.object_storage import (
    ObjectStorageClient,
    RunStorageReference,
)
from cua_agent_kit.core.run_context import RunContext
from cua_agent_kit.discovery.runner import publish_run


@dataclass
class RecordingDatabase(DatabaseClient):
    failure: Exception | None = None
    entries: list[RunAuditEntry] = field(default_factory=list)

    async def create_run(self, entry: RunAuditEntry) -> None:
        raise AssertionError("Publishing must not create a run")

    async def finish_run(self, entry: RunAuditEntry) -> None:
        self.entries.append(entry)
        if self.failure is not None:
            raise self.failure


@dataclass
class RecordingStorage(ObjectStorageClient):
    reference: RunStorageReference = RunStorageReference(
        "azure", "container", "test-run"
    )
    failure: Exception | None = None
    uploads: list[tuple[str, Path]] = field(default_factory=list)

    async def upload_run(self, run_id: str, run_dir: Path) -> RunStorageReference:
        self.uploads.append((run_id, run_dir))
        if self.failure is not None:
            raise self.failure
        assert json.loads((run_dir / "run.json").read_text())["run_id"] == run_id
        return self.reference


@pytest.mark.asyncio
@pytest.mark.parametrize("local", [False, True])
async def test_publish_records_uploaded_reference_and_backend_status(
    context: RunContext, local: bool
) -> None:
    database = RecordingDatabase()
    storage = RecordingStorage()
    if local:
        context.config = replace(context.config, database_backend="none")
        storage.reference = RunStorageReference("local", "artifacts", "test-run")
    await publish_run(context, database, storage)
    assert storage.uploads == [(context.run_id, context.artifacts.run_dir)]
    assert database.entries[0].storage == storage.reference
    assert database.entries[0].status == "completed"
    assert context.upload_status == ("local" if local else "succeeded")
    assert context.audit_status == ("disabled" if local else "succeeded")


@pytest.mark.asyncio
async def test_upload_failure_still_reaches_database(context: RunContext) -> None:
    database = RecordingDatabase()
    storage = RecordingStorage(failure=TimeoutError("storage unavailable"))
    await publish_run(context, database, storage)
    assert context.upload_status == "failed"
    assert database.entries[0].storage is None
    assert database.entries[0].upload_error == "TimeoutError"
    assert context.audit_status == "succeeded"


@pytest.mark.asyncio
async def test_database_failure_preserves_uploaded_result(context: RunContext) -> None:
    database = RecordingDatabase(failure=RuntimeError("database unavailable"))
    storage = RecordingStorage()
    await publish_run(context, database, storage)
    assert context.storage == storage.reference
    assert context.upload_status == "succeeded"
    assert context.audit_status == "failed"
