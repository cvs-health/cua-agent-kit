# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Deterministic referral scheduling and appointment verification."""

from playwright.async_api import Page, expect

from cua_agent_kit.clients.browser.session import BrowserSession
from cua_agent_kit.core.action import Action


async def search_referral(page: Page, session: BrowserSession) -> None:
    await page.get_by_label("Search referrals", exact=True).fill("REF-1001")
    await page.get_by_role("button", name="Search", exact=True).click()
    # Scope the specialty and schedule control to the verified referral card.
    referral = page.get_by_role("article").filter(
        has=page.get_by_role("heading", name="REF-1001 — Jordan Ellis", exact=True)
    )
    await expect(referral).to_have_count(1)
    await expect(
        referral.get_by_text("Physical therapy · Ready to schedule", exact=True)
    ).to_be_visible()
    session.artifacts.record_action(
        Action(
            action="search_referrals",
            url=page.url,
            screenshot=await session.screenshot(),
        )
    )
    await referral.get_by_role("button", name="Schedule REF-1001", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Schedule appointment", exact=True)
    ).to_be_visible()
    await expect(
        page.get_by_text("REF-1001 — Jordan Ellis — Physical therapy", exact=True)
    ).to_be_visible()
    session.artifacts.record_action(
        Action(
            action="select_referral",
            url=page.url,
            screenshot=await session.screenshot(),
        )
    )


async def enter_appointment(page: Page, session: BrowserSession) -> None:
    date = page.get_by_label("Appointment date", exact=True)
    time = page.get_by_label("Appointment time", exact=True)
    await date.fill("2027-04-15")
    await time.fill("09:30")
    await expect(date).to_have_value("2027-04-15")
    await expect(time).to_have_value("09:30")
    session.artifacts.record_action(
        Action(
            action="enter_appointment",
            url=page.url,
            screenshot=await session.screenshot(),
        )
    )


async def verify_success(page: Page) -> str:
    await expect(
        page.get_by_role("heading", name="Appointment confirmed", exact=True)
    ).to_be_visible()
    summary = page.get_by_test_id("appointment-summary")
    await expect(summary).to_be_visible()
    await expect(summary).to_have_text(
        "REF-1001 — Jordan Ellis — Physical therapy — 2027-04-15 at 09:30 — Scheduled"
    )
    return "sample_appointment_verified"


async def run_steps(page: Page, session: BrowserSession) -> str:
    await search_referral(page, session)
    await enter_appointment(page, session)
    await page.get_by_role("button", name="Confirm appointment", exact=True).click()
    result = await verify_success(page)
    session.artifacts.record_action(
        Action(
            action="verify_appointment",
            url=page.url,
            screenshot=await session.screenshot(),
        )
    )
    return result
