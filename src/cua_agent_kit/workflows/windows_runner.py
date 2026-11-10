# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Deploy and execute source-controlled pywinauto steps on an existing VM."""

import asyncio
import base64
import hashlib
import json
import logging
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import PureWindowsPath
from typing import Any

from dotenv import load_dotenv
from mslex import quote

from cua_agent_kit.clients.factory import create_clients
from cua_agent_kit.clients.windows.client import WindowsClient
from cua_agent_kit.core.action import Action
from cua_agent_kit.core.config import load_windows_deterministic_config
from cua_agent_kit.core.logging import configure_logging
from cua_agent_kit.core.run_context import build_run_context
from cua_agent_kit.core.telemetry import emit_run_event
from cua_agent_kit.discovery.runner import publish_run
from cua_agent_kit.workflows.windows_steps import PROMPT_SHA256, STEPS

logger = logging.getLogger(__name__)


async def run() -> None:
    config = load_windows_deterministic_config()
    if hashlib.sha256(config.workflow_prompt.encode()).hexdigest() != PROMPT_SHA256:
        raise RuntimeError("Discovery prompt changed; recodify native steps first")
    database, storage = create_clients(config)
    record = build_run_context("deterministic", config)
    artifacts = record.artifacts
    source = files("cua_agent_kit.workflows").joinpath("windows_steps.py")
    source_bytes = source.read_bytes()
    client = WindowsClient(host=config.windows_host, port=config.windows_port)
    state: dict[str, Any] = {"run_id": record.run_id}
    last_confirmed_step: str | None = None
    active_step: str | None = None
    artifacts.write_run_metadata(
        {**record.metadata(), "workflow": "windows_steps", "backend": "windows"}
    )
    emit_run_event(record, "run_started")
    try:
        await database.create_run(record)
        await client.open()
        artifacts.start(
            metadata={
                "backend": "windows",
                "workflow": "windows_steps",
                "workflow_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "desktop_dimensions": client.dimensions,
            }
        )
        if not client.inspection_info.get("available"):
            raise RuntimeError(
                "Install windows-host inspection dependencies before native replay"
            )
        bootstrap = (
            "import os,json; print(json.dumps(os.path.join("
            "os.environ['LOCALAPPDATA'], 'cua-agent-kit', 'workflows')))"
        )
        result = await client.interface.run_command(f"python -c {quote(bootstrap)}")
        if result.returncode != 0:
            raise RuntimeError("Windows workflow directory lookup failed")
        directory = json.loads(result.stdout)
        await client.interface.create_dir(directory)
        host_path = str(PureWindowsPath(directory) / "windows_steps.py")
        await client.interface.write_bytes(host_path, source_bytes)
        for step in STEPS:
            active_step = step
            logger.info("Windows workflow: %s", step)
            encoded = base64.b64encode(
                json.dumps({"step": step, "state": state}).encode()
            ).decode("ascii")
            response = await client.interface.run_command(
                f"python {quote(host_path)} {encoded}"
            )
            try:
                payload = json.loads(response.stdout)
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("state"), dict
                ):
                    raise ValueError("Invalid workflow acknowledgement")
            except (ValueError, TypeError) as error:
                artifacts.record_action(
                    Action(
                        action=step,
                        outcome="error",
                        details={
                            "error": "Ambiguous acknowledgement; input not replayed",
                            "returncode": response.returncode,
                            "stdout": artifacts.redact(response.stdout),
                            "stderr": artifacts.redact(response.stderr),
                            "last_confirmed_step": last_confirmed_step,
                        },
                        screenshot=await client.screenshot(),
                    )
                )
                raise RuntimeError(
                    f"Ambiguous acknowledgement for {step}; last confirmed step: "
                    f"{last_confirmed_step}; input not replayed"
                ) from error
            state = payload["state"]
            succeeded = response.returncode == 0 and payload.get("ok") is True
            artifacts.record_action(
                Action(
                    action=step,
                    outcome="success" if succeeded else "error",
                    details=payload.get(
                        "result",
                        {
                            "error_type": payload.get("error_type"),
                            "error": artifacts.redact(payload.get("error", "")),
                        },
                    ),
                    screenshot=await client.screenshot(),
                )
            )
            if not succeeded:
                raise RuntimeError(
                    f"Windows workflow step {step} failed "
                    f"({payload.get('error_type', 'unknown')}): "
                    f"{artifacts.redact(payload.get('error', 'No details returned'))}"
                )
            last_confirmed_step = step
            if step == "verify":
                record.terminal_assertion = payload["result"]["terminal_assertion"]
        record.status = "succeeded"
        logger.info("Windows workflow succeeded: %s", record.terminal_assertion)
        logger.info("Saved file: %s", state["saved_file_path"])
    except BaseException as error:
        record.status = "failed"
        record.error_type = type(error).__name__
        record.error = artifacts.redact(f"{type(error).__name__}: {error}")
        raise
    finally:
        # Keep newly created windows available for inspection; never close other
        # applications or replay a failed/ambiguous input automatically.
        artifacts.finish(
            metadata={
                "runtime_windows": state,
                "last_confirmed_step": last_confirmed_step,
                "active_step": active_step,
                "saved_file_path": state.get("saved_file_path"),
            }
        )
        await client.close()
        record.finished_at = datetime.now(UTC)
        await publish_run(record, database, storage)
        emit_run_event(record, "run_finished")


def main() -> None:
    load_dotenv()
    configure_logging()
    asyncio.run(run())
