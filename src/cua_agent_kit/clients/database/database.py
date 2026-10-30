# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cua_agent_kit.clients.object_storage.object_storage import RunStorageReference
from cua_agent_kit.core.run_context import RunContext


@dataclass(frozen=True)
class RunAuditEntry:
    run_id: str
    execution_mode: str
    prompt_sha256: str
    started_at: datetime
    status: str
    finished_at: datetime | None = None
    terminal_assertion: str | None = None
    error: str | None = None
    storage: RunStorageReference | None = None
    upload_error: str | None = None

    @classmethod
    def from_context(
        cls,
        context: RunContext,
    ) -> "RunAuditEntry":
        return cls(
            run_id=context.run_id,
            execution_mode=context.execution_mode,
            prompt_sha256=context.prompt_sha256,
            started_at=context.started_at,
            status=context.status,
            finished_at=context.finished_at,
            terminal_assertion=context.terminal_assertion,
            error=context.error,
            storage=context.storage,
            upload_error=context.upload_error,
        )


class DatabaseClient(Protocol):
    async def create_run(self, entry: RunAuditEntry) -> None: ...

    async def finish_run(self, entry: RunAuditEntry) -> None: ...
