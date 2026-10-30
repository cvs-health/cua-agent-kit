# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from cua_agent_kit.clients.database.database import RunAuditEntry


class NoOpDatabaseClient:
    async def create_run(self, entry: RunAuditEntry) -> None:
        pass

    async def finish_run(self, entry: RunAuditEntry) -> None:
        pass
