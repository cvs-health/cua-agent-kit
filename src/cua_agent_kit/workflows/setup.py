# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Codified login for deterministic runs."""

from playwright.async_api import Page

from cua_agent_kit.clients.browser.session import BrowserSession
from cua_agent_kit.core.action import Action
from cua_agent_kit.core.config import AppConfig


async def setup_workflow(
    page: Page, config: AppConfig, session: BrowserSession
) -> None:
    await page.get_by_label("Username", exact=True).fill(
        config.workflow_credentials.username
    )
    await page.get_by_label("Password", exact=True).fill(
        config.workflow_credentials.password
    )
    await page.get_by_role("button", name="Sign in", exact=True).click()
    await page.get_by_role("heading", name="Referrals", exact=True).wait_for()
    session.artifacts.record_action(
        Action(
            action="setup_workflow",
            url=page.url,
            screenshot=await session.screenshot(),
        )
    )
