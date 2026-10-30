# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from datetime import UTC, datetime

from dotenv import load_dotenv

from cua_agent_kit.clients.database.database import DatabaseClient, RunAuditEntry
from cua_agent_kit.clients.factory import create_clients
from cua_agent_kit.clients.object_storage.object_storage import ObjectStorageClient
from cua_agent_kit.core.browser import BrowserSession
from cua_agent_kit.core.config import AppConfig, load_deterministic_config
from cua_agent_kit.core.logging import configure_logging
from cua_agent_kit.core.run_context import build_run_context
from cua_agent_kit.core.telemetry import emit_run_event
from cua_agent_kit.workflows.setup import setup_workflow
from cua_agent_kit.workflows.steps import run_steps

logger = logging.getLogger(__name__)


class DeterministicWorkflow:
    def __init__(
        self, config: AppConfig, database: DatabaseClient, storage: ObjectStorageClient
    ) -> None:
        self.config = config
        self.database = database
        self.storage = storage
        self.context = build_run_context("deterministic", config)
        self.artifacts = self.context.artifacts
        self.session = BrowserSession(
            start_url=config.start_url,
            headless=config.playwright_headless,
            artifacts=self.artifacts,
        )

    async def run(self) -> None:
        record = self.context
        self.artifacts.write_run_metadata(record.metadata())
        record.status = "running"
        status = "failed"
        terminal_assertion: str | None = None
        emit_run_event(record, "run_started")
        try:
            await self.database.create_run(RunAuditEntry.from_context(record))
            logger.info("Starting deterministic run %s", record.run_id)
            await self.session.open()
            page = self.session.page
            await setup_workflow(page, self.config, self.artifacts)
            terminal_assertion = await self.run_workflow()

            status = "succeeded"
            logger.info("Deterministic run %s succeeded", record.run_id)
        except Exception as exception:
            record.error_type = type(exception).__name__
            record.error = self.artifacts.redact(
                f"{type(exception).__name__}: {exception}"
            )
            logger.error(
                "Deterministic run %s failed: %s",
                record.run_id,
                type(exception).__name__,
            )
            raise
        finally:
            finished_at = datetime.now(UTC)
            record.status = status
            record.finished_at = finished_at
            record.terminal_assertion = terminal_assertion
            try:
                if self.session.is_open:
                    await self.session.finish_artifacts(record.status)
            except Exception as artifact_error:
                logger.warning(
                    "Artifact finalization failed: %s", type(artifact_error).__name__
                )
            try:
                await self.session.close()
            except Exception as exception:
                logger.warning("Browser cleanup failed: %s", type(exception).__name__)
            await self.publish_run()
            emit_run_event(record, "run_finished")

    async def publish_run(self) -> None:
        record = self.context
        try:
            self.artifacts.write_run_metadata(record.metadata())
        except Exception as exception:
            logger.error("Run metadata write failed: %s", type(exception).__name__)
        try:
            record.storage = await self.storage.upload_run(
                record.run_id, self.artifacts.run_dir
            )
            record.upload_status = (
                "local" if record.storage.backend == "local" else "succeeded"
            )
        except Exception as exception:
            record.upload_status = "failed"
            record.upload_error = type(exception).__name__
            logger.error("Run upload failed: %s", record.upload_error)
        try:
            await self.database.finish_run(RunAuditEntry.from_context(record))
            record.audit_status = (
                "succeeded" if self.config.database_backend != "none" else "disabled"
            )
        except Exception as exception:
            record.audit_status = "failed"
            logger.error("Database finalization failed: %s", type(exception).__name__)

    async def run_workflow(self) -> str:
        """Extend the authenticated workflow and verify its terminal state here."""
        return await run_steps(self.session.page, self.artifacts)


async def run() -> None:
    config = load_deterministic_config()
    database, storage = create_clients(config)
    await DeterministicWorkflow(config, database, storage).run()


def main() -> None:
    load_dotenv()
    configure_logging()
    asyncio.run(run())
