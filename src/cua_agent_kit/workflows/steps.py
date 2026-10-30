# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Deterministic referral scheduling and appointment verification."""

from playwright.async_api import Page, expect

from cua_agent_kit.core.artifacts import RunArtifacts


async def search_referral(page: Page, artifacts: RunArtifacts) -> None:
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
    await artifacts.record_action(page, action="search_referrals")
    await referral.get_by_role("button", name="Schedule REF-1001", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Schedule appointment", exact=True)
    ).to_be_visible()
    await expect(
        page.get_by_text("REF-1001 — Jordan Ellis — Physical therapy", exact=True)
    ).to_be_visible()
    await artifacts.record_action(page, action="select_referral")


async def enter_appointment(page: Page, artifacts: RunArtifacts) -> None:
    date = page.get_by_label("Appointment date", exact=True)
    time = page.get_by_label("Appointment time", exact=True)
    await date.fill("2027-04-15")
    await time.fill("09:30")
    await expect(date).to_have_value("2027-04-15")
    await expect(time).to_have_value("09:30")
    await artifacts.record_action(page, action="enter_appointment")


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


async def run_steps(page: Page, artifacts: RunArtifacts) -> str:
    await search_referral(page, artifacts)
    await enter_appointment(page, artifacts)
    await page.get_by_role("button", name="Confirm appointment", exact=True).click()
    result = await verify_success(page)
    await artifacts.record_action(page, action="verify_appointment")
    return result
