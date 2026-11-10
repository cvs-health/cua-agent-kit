# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncpg

from cua_agent_kit.core.run_context import RunContext


class PostgresDatabaseClient:
    def __init__(self, jdbc_uri: str, user: str) -> None:
        if not jdbc_uri.startswith("jdbc:postgresql://"):
            raise ValueError("Expected a PostgreSQL JDBC URI.")
        self.dsn = jdbc_uri.removeprefix("jdbc:")
        self.user = user

    async def create_run(self, context: RunContext) -> None:
        connection = await asyncpg.connect(self.dsn, user=self.user, timeout=15)
        try:
            await connection.execute(
                """INSERT INTO workflow_runs
                (run_id, execution_mode, prompt_sha256, started_at, status)
                VALUES ($1, $2, $3, $4, $5) ON CONFLICT (run_id) DO NOTHING""",
                context.run_id,
                context.execution_mode,
                context.prompt_sha256,
                context.started_at,
                context.status,
                timeout=30,
            )
        finally:
            await connection.close()

    async def finish_run(self, context: RunContext) -> None:
        connection = await asyncpg.connect(self.dsn, user=self.user, timeout=15)
        try:
            await connection.execute(
                """UPDATE workflow_runs SET status=$2, finished_at=$3,
                terminal_assertion=$4, error=$5, storage_backend=$6,
                storage_namespace=$7, storage_prefix=$8, upload_error=$9
                WHERE run_id=$1""",
                context.run_id,
                context.status,
                context.finished_at,
                context.terminal_assertion,
                context.error,
                context.storage_backend,
                context.storage_namespace,
                context.storage_prefix,
                context.upload_error,
                timeout=30,
            )
        finally:
            await connection.close()
