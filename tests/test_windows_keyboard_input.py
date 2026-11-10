# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from cua_agent_kit.clients.windows.keyboard_input import virtual_key_plan


def test_capitals_and_shifted_punctuation_use_real_modifiers():
    assert virtual_key_plan("W", 0x0157, False) == (0x57, [0x10])
    assert virtual_key_plan("!", 0x0131, False) == (0x31, [0x10])
    assert virtual_key_plan("w", 0x0057, False) == (0x57, [])


def test_caps_lock_is_accounted_for_without_toggling_it():
    assert virtual_key_plan("W", 0x0157, True) == (0x57, [])
    assert virtual_key_plan("w", 0x0057, True) == (0x57, [0x10])


def test_unmapped_unicode_and_control_characters_are_distinguished():
    assert virtual_key_plan("—", -1, False) is None
    assert virtual_key_plan("\n", -1, False) == (0x0D, [])
    assert virtual_key_plan("\t", -1, False) == (0x09, [])
