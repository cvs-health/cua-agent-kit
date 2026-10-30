# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Edit this prompt to discover your own browser workflow."""


def workflow_prompt(username: str, password: str) -> str:

    prompt = f"""
Sign in with username {username} and password {password}.

Search referrals for REF-1001. Verify it is for Jordan Ellis, Physical therapy.
Schedule an appointment for 2027-04-15 at 09:30 and confirm it.

Verify the appointment confirmed page shows REF-1001, Jordan Ellis, Physical therapy,
2027-04-15 at 09:30, and Scheduled.

Stop after confirmation.
"""
    return prompt.strip()
