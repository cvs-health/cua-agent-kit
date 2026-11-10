# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Edit this prompt to discover your own browser or Windows workflow."""


def workflow_prompt(username: str, password: str) -> str:

    # web workflow prompt
    prompt = f"""
        Sign in with username {username} and password {password}.

        Search referrals for REF-1001. Verify it is for Jordan Ellis, Physical therapy.
        Schedule an appointment for 2027-04-15 at 09:30 and confirm it.

        Verify the appointment confirmed page shows REF-1001, Jordan Ellis,
        Physical therapy,
        2027-04-15 at 09:30, and Scheduled.

        Stop after confirmation.
    """

    # windows prompt, uncomment for Windows workflows
    # prompt = """
    #     1. Open a new Notepad window.
    #     2. Type exactly these three lines:
    #        Windows native workflow test!
    #        ABC xyz 123 — café
    #        Saved and reopened successfully.
    #     3. Drag Notepad by its title bar to the left side of the desktop.
    #     4. Open Save As.
    #     5. Save the document in the Windows user's Documents folder as
    #        cua-native-test-<current date and time>.txt.
    #        Use UTF-8 encoding. Do not overwrite an existing file.
    #     6. Close only the Notepad window you created.
    #     7. Open a new Notepad window and use its Open dialog to reopen that file.
    #     8. Verify that all three lines match exactly, including capitalization,
    #        punctuation, the em dash, and the accented character.
    #     9. Take a screenshot of the reopened document.
    #     10. Report the full saved file path.
    # """

    return prompt.strip()
