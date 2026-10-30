# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Codified login for deterministic runs."""

from playwright.async_api import Page

from cua_agent_kit.core.artifacts import RunArtifacts
from cua_agent_kit.core.config import AppConfig


async def setup_workflow(
    page: Page, config: AppConfig, artifacts: RunArtifacts
) -> None:
    await page.get_by_label("Username", exact=True).fill(
        config.workflow_credentials.username
    )
    await page.get_by_label("Password", exact=True).fill(
        config.workflow_credentials.password
    )
    await page.get_by_role("button", name="Sign in", exact=True).click()
    await page.get_by_role("heading", name="Referrals", exact=True).wait_for()
    await artifacts.record_action(page, action="setup_workflow")
