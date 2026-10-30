# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncpg

from cua_agent_kit.clients.database.database import RunAuditEntry


class PostgresDatabaseClient:
    def __init__(self, jdbc_uri: str, user: str) -> None:
        if not jdbc_uri.startswith("jdbc:postgresql://"):
            raise ValueError("Expected a PostgreSQL JDBC URI.")
        self.dsn = jdbc_uri.removeprefix("jdbc:")
        self.user = user

    async def create_run(self, entry: RunAuditEntry) -> None:
        connection = await asyncpg.connect(self.dsn, user=self.user, timeout=15)
        try:
            await connection.execute(
                """INSERT INTO workflow_runs
                (run_id, execution_mode, prompt_sha256, started_at, status)
                VALUES ($1, $2, $3, $4, $5) ON CONFLICT (run_id) DO NOTHING""",
                entry.run_id,
                entry.execution_mode,
                entry.prompt_sha256,
                entry.started_at,
                entry.status,
                timeout=30,
            )
        finally:
            await connection.close()

    async def finish_run(self, entry: RunAuditEntry) -> None:
        connection = await asyncpg.connect(self.dsn, user=self.user, timeout=15)
        storage = entry.storage
        try:
            await connection.execute(
                """UPDATE workflow_runs SET status=$2, finished_at=$3,
                terminal_assertion=$4, error=$5, storage_backend=$6,
                storage_namespace=$7, storage_prefix=$8, upload_error=$9
                WHERE run_id=$1""",
                entry.run_id,
                entry.status,
                entry.finished_at,
                entry.terminal_assertion,
                entry.error,
                storage.backend if storage else None,
                storage.namespace if storage else None,
                storage.prefix if storage else None,
                entry.upload_error,
                timeout=30,
            )
        finally:
            await connection.close()
