# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from cua_agent_kit.clients.object_storage.object_storage import RunStorageReference


class LocalObjectStorageClient:
    async def upload_run(self, run_id: str, run_dir: Path) -> RunStorageReference:
        return RunStorageReference("local", str(run_dir.parent.resolve()), run_dir.name)
