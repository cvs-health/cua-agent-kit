# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

import pytest

from cua_agent_kit.core.config import load_config, load_deterministic_config
from cua_agent_kit.discovery.prompt import workflow_prompt


def test_windows_does_not_require_browser_account(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("WORKFLOW_ACCOUNT_JSON", "not json")
    monkeypatch.setenv("DATABASE_BACKEND", "none")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DISCOVERY_BACKEND", "windows")
    monkeypatch.setenv("WINDOWS_HOST", "example")
    monkeypatch.setenv("WORKFLOW_PROMPT", "ignored environment override")
    monkeypatch.setenv("MAX_TURNS", "999")
    config = load_config()
    assert config.workflow_prompt == workflow_prompt("", "")
    assert config.max_turns == 40
    assert config.windows_host == "example"
    assert config.workflow_credentials.username == ""
    assert config.workflow_credentials.password == ""
    assert config.start_url == ""


def test_deterministic_stays_browser_when_windows_discovery_is_selected(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DISCOVERY_BACKEND", "windows")
    monkeypatch.setenv("WINDOWS_PORT", "invalid but irrelevant to browser execution")
    monkeypatch.setenv("DATABASE_BACKEND", "none")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "local")
    config = load_deterministic_config()
    assert config.discovery_backend == "browser"
    assert config.start_url
