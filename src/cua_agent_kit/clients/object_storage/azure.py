# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import asyncio
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from cua_agent_kit.clients.object_storage.object_storage import RunStorageReference


class AzureObjectStorageClient:
    def __init__(self, account_url: str, container: str) -> None:
        self.account_url = account_url
        self.container = container

    async def upload_run(self, run_id: str, run_dir: Path) -> RunStorageReference:
        if not run_dir.is_dir():
            raise FileNotFoundError("Run artifact directory does not exist.")
        async with DefaultAzureCredential() as credential:
            async with BlobServiceClient(
                self.account_url,
                credential=credential,
                retry_total=3,
                connection_timeout=15,
                read_timeout=30,
            ) as service:
                container = service.get_container_client(self.container)
                for path in sorted(run_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    content_type = {
                        ".png": "image/png",
                        ".zip": "application/zip",
                        ".json": "application/json",
                        ".jsonl": "application/x-ndjson",
                    }.get(path.suffix, "application/octet-stream")
                    with path.open("rb") as data:
                        await asyncio.wait_for(
                            container.upload_blob(
                                name=f"{run_id}/{path.relative_to(run_dir).as_posix()}",
                                data=data,
                                overwrite=True,
                                content_settings=ContentSettings(
                                    content_type=content_type
                                ),
                            ),
                            timeout=120,
                        )
        return RunStorageReference("azure", self.container, run_id)
