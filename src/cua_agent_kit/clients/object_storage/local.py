# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from cua_agent_kit.core.run_context import RunContext


class LocalObjectStorageClient:
    async def upload_run(self, context: RunContext) -> None:
        run_dir = context.artifacts.run_dir
        context.storage_backend = "local"
        context.storage_namespace = str(run_dir.parent.resolve())
        context.storage_prefix = run_dir.name
        context.upload_status = "local"
        context.upload_error = None
