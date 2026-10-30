# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RunStorageReference:
    backend: str
    namespace: str
    prefix: str


class ObjectStorageClient(Protocol):
    async def upload_run(self, run_id: str, run_dir: Path) -> RunStorageReference: ...
