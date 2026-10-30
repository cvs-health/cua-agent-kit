# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cua_agent_kit.discovery.prompt import workflow_prompt


@dataclass(frozen=True)
class WorkflowCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class AppConfig:
    playwright_headless: bool
    max_turns: int
    workflow_credentials: WorkflowCredentials
    artifacts_dir: Path
    deterministic_artifacts_dir: Path
    workflow_prompt: str
    start_url: str
    database_backend: str = "none"
    database_jdbc_uri: str = ""
    database_user: str = ""
    object_storage_backend: str = "local"
    azure_storage_account_url: str = ""
    azure_storage_container: str = ""


def load_config() -> AppConfig:
    _require_env("OPENAI_API_KEY")
    return _build_config()


def load_deterministic_config() -> AppConfig:
    return _build_config()


def _build_config() -> AppConfig:
    workflow_credentials = _load_workflow_credentials()
    database_backend = os.getenv("DATABASE_BACKEND", "none").strip()
    storage_backend = os.getenv("OBJECT_STORAGE_BACKEND", "local").strip()
    if database_backend not in {"none", "postgres"}:
        raise SystemExit("DATABASE_BACKEND must be none or postgres.")
    if storage_backend not in {"local", "azure"}:
        raise SystemExit("OBJECT_STORAGE_BACKEND must be local or azure.")
    return AppConfig(
        playwright_headless=_env_flag("PLAYWRIGHT_HEADLESS", default=False),
        max_turns=int(os.getenv("MAX_TURNS", "40")),
        workflow_credentials=workflow_credentials,
        artifacts_dir=Path(os.getenv("ARTIFACTS_DIR", "artifacts/discovery")),
        deterministic_artifacts_dir=Path(
            os.getenv("DETERMINISTIC_ARTIFACTS_DIR", "artifacts/deterministic")
        ),
        workflow_prompt=workflow_prompt(
            workflow_credentials.username, workflow_credentials.password
        ),
        start_url=os.getenv("START_URL", "http://127.0.0.1:8081"),
        database_backend=database_backend,
        database_jdbc_uri=_require_env("DATABASE_JDBC_URI")
        if database_backend == "postgres"
        else "",
        database_user=_require_env("DATABASE_USER")
        if database_backend == "postgres"
        else "",
        object_storage_backend=storage_backend,
        azure_storage_account_url=(
            _require_env("AZURE_STORAGE_ACCOUNT_URL")
            if storage_backend == "azure"
            else ""
        ),
        azure_storage_container=(
            _require_env("AZURE_STORAGE_CONTAINER")
            if storage_backend == "azure"
            else ""
        ),
    )


def _load_workflow_credentials() -> WorkflowCredentials:
    try:
        account = json.loads(
            os.getenv(
                "WORKFLOW_ACCOUNT_JSON",
                '{"username":"demo","password":"demo-password"}',
            )
        )
        username = str(account.get("username", "")).strip()
        password = str(account.get("password", ""))
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit(
            "WORKFLOW_ACCOUNT_JSON must be JSON with username and password fields."
        ) from error

    return WorkflowCredentials(username=username, password=password)


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise SystemExit(f"Set {name} in your environment or .env file.")
