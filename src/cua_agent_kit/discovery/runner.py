# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from datetime import UTC, datetime

from dotenv import load_dotenv

from cua_agent_kit.clients.database.database import DatabaseClient, RunAuditEntry
from cua_agent_kit.clients.factory import create_clients
from cua_agent_kit.clients.object_storage.object_storage import ObjectStorageClient
from cua_agent_kit.core.config import load_config
from cua_agent_kit.core.logging import configure_logging
from cua_agent_kit.core.run_context import RunContext, build_run_context
from cua_agent_kit.core.telemetry import emit_run_event
from cua_agent_kit.discovery.agent import BrowserAgent

logger = logging.getLogger(__name__)


async def run() -> None:
    config = load_config()
    logger.info("Discovery model configured")
    database, storage = create_clients(config)
    record = build_run_context("discovery", config)
    artifacts = record.artifacts
    agent = BrowserAgent(record)
    artifacts.write_run_metadata(record.metadata())
    emit_run_event(record, "run_started")
    try:
        await database.create_run(RunAuditEntry.from_context(record))
        logger.info("Starting discovery run %s", record.run_id)
        await agent.run()
    except Exception as exception:
        record.status = "failed"
        record.error_type = type(exception).__name__
        record.error = artifacts.redact(f"{type(exception).__name__}: {exception}")
        logger.error(
            "Discovery run %s failed: %s", record.run_id, type(exception).__name__
        )
        raise
    finally:
        record.finished_at = datetime.now(UTC)
        await publish_run(record, database, storage)
        emit_run_event(record, "run_finished")


async def publish_run(
    context: RunContext,
    database: DatabaseClient,
    storage: ObjectStorageClient,
) -> None:
    try:
        context.artifacts.write_run_metadata(context.metadata())
    except Exception as exception:
        logger.error("Run metadata write failed: %s", type(exception).__name__)
    try:
        context.storage = await storage.upload_run(
            context.run_id, context.artifacts.run_dir
        )
        context.upload_status = (
            "local" if context.storage.backend == "local" else "succeeded"
        )
    except Exception as exception:
        context.upload_status = "failed"
        context.upload_error = type(exception).__name__
        logger.error("Run upload failed: %s", context.upload_error)
    try:
        await database.finish_run(RunAuditEntry.from_context(context))
        context.audit_status = (
            "succeeded" if context.config.database_backend != "none" else "disabled"
        )
    except Exception as exception:
        context.audit_status = "failed"
        logger.error("Database finalization failed: %s", type(exception).__name__)


def main() -> None:
    load_dotenv()
    configure_logging()
    asyncio.run(run())
