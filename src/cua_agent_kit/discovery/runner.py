# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from datetime import UTC, datetime

from dotenv import load_dotenv

from cua_agent_kit.clients.database.database import DatabaseClient
from cua_agent_kit.clients.factory import create_clients
from cua_agent_kit.clients.object_storage.object_storage import ObjectStorageClient
from cua_agent_kit.clients.windows.client import WindowsClient
from cua_agent_kit.core.config import load_config
from cua_agent_kit.core.logging import configure_logging
from cua_agent_kit.core.run_context import RunContext, build_run_context
from cua_agent_kit.core.telemetry import emit_run_event
from cua_agent_kit.discovery.agent import ComputerAgent
from cua_agent_kit.discovery.computer import PlaywrightComputer
from cua_agent_kit.discovery.windows_computer import WindowsComputer

logger = logging.getLogger(__name__)


async def run() -> None:
    config = load_config()
    logger.info("Discovery model configured")
    database, storage = create_clients(config)
    record = build_run_context("discovery", config)
    artifacts = record.artifacts
    computer: PlaywrightComputer | WindowsComputer
    if config.discovery_backend == "windows":
        computer = WindowsComputer(
            artifacts=artifacts,
            client=WindowsClient(host=config.windows_host, port=config.windows_port),
        )
    else:
        computer = PlaywrightComputer(
            start_url=config.start_url,
            headless=config.playwright_headless,
            artifacts=artifacts,
        )
    agent = ComputerAgent(
        computer,
        model=config.discovery_model,
        sensitive_values=(
            config.workflow_credentials.username,
            config.workflow_credentials.password,
        ),
    )
    await execute_run(record, computer, agent, database, storage)


async def execute_run(
    record: RunContext,
    computer: PlaywrightComputer | WindowsComputer,
    agent: ComputerAgent,
    database: DatabaseClient,
    storage: ObjectStorageClient,
) -> None:
    config = record.config
    artifacts = record.artifacts
    artifacts.write_run_metadata(record.metadata())
    emit_run_event(record, "run_started")
    try:
        await database.create_run(record)
        logger.info("Starting discovery run %s", record.run_id)
        await computer.open()
        logger.info("Computer opened; starting discovery run")
        final_output = await agent.run(
            prompt=config.workflow_prompt, max_turns=config.max_turns
        )
        record.final_output = artifacts.redact(final_output)
        record.status = "completed"
        logger.info("Discovery run completed")
    except BaseException as exception:
        record.status = "failed"
        record.error_type = type(exception).__name__
        record.error = artifacts.redact(f"{type(exception).__name__}: {exception}")
        logger.error(
            "Discovery run %s failed: %s", record.run_id, type(exception).__name__
        )
        raise
    finally:
        try:
            if computer.is_open:
                await computer.finish_artifacts(record.status)
        except Exception as exception:
            logger.warning("Artifact finalization failed: %s", type(exception).__name__)
        finally:
            try:
                await computer.close()
            except Exception as exception:
                logger.warning("Computer cleanup failed: %s", type(exception).__name__)
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
        await storage.upload_run(context)
    except Exception as exception:
        context.upload_status = "failed"
        context.upload_error = type(exception).__name__
        logger.error("Run upload failed: %s", context.upload_error)
    try:
        await database.finish_run(context)
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
