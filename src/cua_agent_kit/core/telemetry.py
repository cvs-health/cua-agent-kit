# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Allowlisted operational events derived from the authoritative run context."""

import json
import logging
from datetime import UTC, datetime
from typing import Literal

from cua_agent_kit.core.run_context import RunContext

logger = logging.getLogger("cua_agent_kit.events")


def emit_run_event(
    context: RunContext, event: Literal["run_started", "run_finished"]
) -> None:
    payload = {
        "schema_version": 1,
        "source": "cua_agent_kit",
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "info",
        "event": event,
        "run_id": context.run_id,
        "execution_mode": context.execution_mode,
    }
    if event == "run_finished":
        payload.update(
            status="succeeded" if context.status == "completed" else context.status,
            duration_seconds=context.duration_seconds,
            error_type=context.error_type,
            upload_status=context.upload_status,
            audit_status=context.audit_status,
        )
    logger.info(json.dumps(payload, separators=(",", ":")))
