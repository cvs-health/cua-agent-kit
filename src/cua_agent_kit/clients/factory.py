# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from cua_agent_kit.clients.database.database import DatabaseClient
from cua_agent_kit.clients.database.local import NoOpDatabaseClient
from cua_agent_kit.clients.database.postgres import PostgresDatabaseClient
from cua_agent_kit.clients.object_storage.azure import AzureObjectStorageClient
from cua_agent_kit.clients.object_storage.local import LocalObjectStorageClient
from cua_agent_kit.clients.object_storage.object_storage import ObjectStorageClient
from cua_agent_kit.core.config import AppConfig


def create_clients(config: AppConfig) -> tuple[DatabaseClient, ObjectStorageClient]:
    database: DatabaseClient = NoOpDatabaseClient()
    storage: ObjectStorageClient = LocalObjectStorageClient()
    if config.database_backend == "postgres":
        database = PostgresDatabaseClient(
            config.database_jdbc_uri, config.database_user
        )
    if config.object_storage_backend == "azure":
        storage = AzureObjectStorageClient(
            config.azure_storage_account_url, config.azure_storage_container
        )
    return database, storage
