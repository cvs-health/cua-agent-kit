# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

from cua_agent_kit.core.run_context import RunContext


class DatabaseClient(Protocol):
    async def create_run(self, context: RunContext) -> None: ...

    async def finish_run(self, context: RunContext) -> None: ...
