# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
from dataclasses import dataclass, field, replace
from unittest.mock import AsyncMock

import pytest

from cua_agent_kit.clients.database.database import DatabaseClient
from cua_agent_kit.clients.database.postgres import PostgresDatabaseClient
from cua_agent_kit.clients.object_storage.azure import AzureObjectStorageClient
from cua_agent_kit.clients.object_storage.local import LocalObjectStorageClient
from cua_agent_kit.clients.object_storage.object_storage import ObjectStorageClient
from cua_agent_kit.core.run_context import RunContext
from cua_agent_kit.discovery.runner import publish_run
from cua_agent_kit.workflows.runner import DeterministicWorkflow


@dataclass
class RecordingDatabase(DatabaseClient):
    failure: Exception | None = None
    entries: list[RunContext] = field(default_factory=list)

    async def create_run(self, context: RunContext) -> None:
        raise AssertionError("Publishing must not create a run")

    async def finish_run(self, context: RunContext) -> None:
        self.entries.append(replace(context))
        if self.failure is not None:
            raise self.failure


@dataclass
class RecordingStorage(ObjectStorageClient):
    failure: Exception | None = None
    uploads: list[RunContext] = field(default_factory=list)

    async def upload_run(self, context: RunContext) -> None:
        self.uploads.append(context)
        if self.failure is not None:
            raise self.failure
        metadata = json.loads((context.artifacts.run_dir / "run.json").read_text())
        assert metadata["run_id"] == context.run_id
        context.storage_backend = "azure"
        context.storage_namespace = "container"
        context.storage_prefix = context.run_id
        context.upload_status = "succeeded"
        context.upload_error = None


@pytest.fixture(params=["discovery", "deterministic"])
def publisher(request: pytest.FixtureRequest):
    if request.param == "discovery":
        return publish_run

    async def publish(context, database, storage):
        workflow = DeterministicWorkflow(context.config, database, storage)
        workflow.context = context
        workflow.artifacts = context.artifacts
        await workflow.publish_run()

    return publish


@pytest.mark.asyncio
@pytest.mark.parametrize("local", [False, True])
async def test_publish_passes_context_with_location_to_database(
    context: RunContext, local: bool, publisher
) -> None:
    database = RecordingDatabase()
    storage = LocalObjectStorageClient() if local else RecordingStorage()
    if local:
        context.config = replace(context.config, database_backend="none")
    await publisher(context, database, storage)
    assert database.entries[0].run_id == context.run_id
    published = database.entries[0]
    assert published.status == "completed"
    assert published.storage_backend == ("local" if local else "azure")
    assert published.storage_namespace == (
        str(context.artifacts.run_dir.parent.resolve()) if local else "container"
    )
    assert published.storage_prefix == (
        context.artifacts.run_dir.name if local else context.run_id
    )
    assert published.upload_status == ("local" if local else "succeeded")
    assert context.audit_status == ("disabled" if local else "succeeded")
    if isinstance(storage, RecordingStorage):
        assert storage.uploads == [context]


@pytest.mark.asyncio
async def test_upload_failure_still_reaches_database(
    context: RunContext, publisher
) -> None:
    database = RecordingDatabase()
    storage = RecordingStorage(failure=TimeoutError("storage unavailable"))
    await publisher(context, database, storage)
    assert context.upload_status == "failed"
    assert database.entries[0].run_id == context.run_id
    assert context.storage_backend is None
    assert context.storage_namespace is None
    assert context.storage_prefix is None
    assert context.upload_error == "TimeoutError"
    assert database.entries[0].upload_status == "failed"
    assert database.entries[0].upload_error == "TimeoutError"
    assert context.audit_status == "succeeded"


@pytest.mark.asyncio
async def test_database_failure_preserves_uploaded_result(
    context: RunContext, publisher
) -> None:
    database = RecordingDatabase(failure=RuntimeError("database unavailable"))
    await publisher(context, database, RecordingStorage())
    assert context.storage_backend == "azure"
    assert context.storage_namespace == "container"
    assert context.storage_prefix == context.run_id
    assert context.upload_status == "succeeded"
    assert context.audit_status == "failed"


@pytest.mark.asyncio
async def test_postgres_maps_context_to_existing_columns(
    context: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = AsyncMock()
    monkeypatch.setattr(
        "cua_agent_kit.clients.database.postgres.asyncpg.connect",
        AsyncMock(return_value=connection),
    )
    database = PostgresDatabaseClient("jdbc:postgresql://localhost/test", "test")
    await database.create_run(context)
    assert connection.execute.call_args.args[1:] == (
        context.run_id,
        context.execution_mode,
        context.prompt_sha256,
        context.started_at,
        context.status,
    )
    context.storage_backend = "azure"
    context.storage_namespace = "container"
    context.storage_prefix = context.run_id
    await database.finish_run(context)
    assert connection.execute.call_args.args[1:] == (
        context.run_id,
        context.status,
        context.finished_at,
        context.terminal_assertion,
        context.error,
        "azure",
        "container",
        context.run_id,
        context.upload_error,
    )
    assert connection.close.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_azure_updates_context_only_after_upload(
    context: RunContext, monkeypatch: pytest.MonkeyPatch, fails: bool
) -> None:
    context.artifacts.write_run_metadata(context.metadata())
    container = AsyncMock()
    if fails:
        container.upload_blob.side_effect = TimeoutError("unavailable")
    service = AsyncMock()
    service.get_container_client = lambda name: container
    service_manager = AsyncMock()
    service_manager.__aenter__.return_value = service
    monkeypatch.setattr(
        "cua_agent_kit.clients.object_storage.azure.DefaultAzureCredential",
        lambda: AsyncMock(),
    )
    monkeypatch.setattr(
        "cua_agent_kit.clients.object_storage.azure.BlobServiceClient",
        lambda *args, **kwargs: service_manager,
    )
    storage = AzureObjectStorageClient("https://example.blob.core.windows.net", "runs")
    if fails:
        with pytest.raises(TimeoutError):
            await storage.upload_run(context)
        assert context.storage_backend is None
        assert context.upload_status == "not_attempted"
    else:
        await storage.upload_run(context)
        assert context.storage_backend == "azure"
        assert context.storage_namespace == "runs"
        assert context.storage_prefix == context.run_id
        assert context.upload_status == "succeeded"
    assert (
        container.upload_blob.call_args.kwargs["name"] == f"{context.run_id}/run.json"
    )
