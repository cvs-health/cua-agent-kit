# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from cua_agent_kit.core.run_context import RunContext


class NoOpDatabaseClient:
    async def create_run(self, context: RunContext) -> None:
        pass

    async def finish_run(self, context: RunContext) -> None:
        pass
