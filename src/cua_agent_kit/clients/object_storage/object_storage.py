# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

from cua_agent_kit.core.run_context import RunContext


class ObjectStorageClient(Protocol):
    """Publish artifacts and set context location/status only after success."""

    async def upload_run(self, context: RunContext) -> None: ...
