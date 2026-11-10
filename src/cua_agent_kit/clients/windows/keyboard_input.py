# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Host-side literal text input using the foreground window's keyboard layout.

CUA's pynput typing uses Unicode packets for shifted characters, which legacy
console windows can drop. Use real virtual keys and modifiers for characters
available in the keyboard layout, retaining Unicode input for other characters.
"""

import base64
import importlib
import json
import sys
import time


def virtual_key_plan(
    character: str, mapping: int, caps_lock: bool
) -> tuple[int, list[int]] | None:
    if character == "\n":
        return 0x0D, []
    if character == "\t":
        return 0x09, []
    if mapping == -1:
        return None
    key = mapping & 0xFF
    shift_state = (mapping >> 8) & 0xFF
    if shift_state & ~7:
        return None
    if 0x41 <= key <= 0x5A and caps_lock:
        shift_state ^= 1
    modifiers = [
        vk for flag, vk in ((1, 0x10), (2, 0x11), (4, 0x12)) if shift_state & flag
    ]
    return key, modifiers


def type_literal(text: str) -> None:
    ctypes = importlib.import_module("ctypes")
    wintypes = importlib.import_module("ctypes.wintypes")
    win32api = importlib.import_module("win32api")
    win32gui = importlib.import_module("win32gui")
    win32process = importlib.import_module("win32process")
    user32 = getattr(ctypes, "WinDLL")("user32", use_last_error=True)
    user32.VkKeyScanExW.argtypes = [wintypes.WCHAR, wintypes.HKL]
    user32.VkKeyScanExW.restype = ctypes.c_short
    foreground = win32gui.GetForegroundWindow()
    if not foreground:
        raise RuntimeError("No interactive foreground window for Windows text input")
    thread_id, _ = win32process.GetWindowThreadProcessId(foreground)
    layout = win32api.GetKeyboardLayout(thread_id)
    keyboard = importlib.import_module("pynput.keyboard").Controller()
    for character in text:
        mapping = (
            user32.VkKeyScanExW(character, layout) if ord(character) <= 0xFFFF else -1
        )
        plan = virtual_key_plan(
            character, mapping, bool(win32api.GetKeyState(0x14) & 1)
        )
        if plan is None:
            keyboard.type(character)
        else:
            key, modifiers = plan
            held = []
            try:
                for modifier in modifiers:
                    if not win32api.GetAsyncKeyState(modifier) & 0x8000:
                        held.append(modifier)
                        win32api.keybd_event(modifier, 0, 0)
                try:
                    win32api.keybd_event(key, 0, 0)
                finally:
                    win32api.keybd_event(key, 0, 2)
            finally:
                for modifier in reversed(held):
                    win32api.keybd_event(modifier, 0, 2)
        time.sleep(0.005)


def main() -> None:
    request = json.loads(base64.b64decode(sys.argv[1], validate=True))
    type_literal(request["text"])
    print(json.dumps({"character_count": len(request["text"])}))


if __name__ == "__main__":
    main()
