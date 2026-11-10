# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Bounded native Notepad save/reopen steps, executed in the Windows session.

Observed classic Notepad selectors are checked for uniqueness in fresh runtime
window/process scopes. Windows-only dependencies are imported only in VM steps.
"""

import base64
import hashlib
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROMPT_SHA256 = "affcd37fbf7492a8f38ce34fa20be016fdf6197c64d3d6204c64356a31262296"
EDITOR = {"auto_id": "15", "control_type": "Edit"}
FINAL_TEXT = (
    "Windows native workflow test!\r\n"
    "ABC xyz 123 — café\r\n"
    "Saved and reopened successfully."
)


def wait_until(check: Any, description: str, timeout: float = 4) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {description}")
        time.sleep(0.1)


def unique(scope: Any, **criteria: Any) -> Any:
    # UIAWrapper.descendants supports control_type, not WindowSpecification's
    # auto_id/title aliases. Filter native properties without reading edit labels.
    controls = scope.descendants(control_type=criteria.get("control_type"))
    properties = {"auto_id": "automation_id", "title": "name"}
    controls = [
        control
        for control in controls
        if all(
            getattr(control.element_info, properties.get(key, key)) == value
            for key, value in criteria.items()
        )
    ]
    if len(controls) != 1:
        raise RuntimeError(
            f"Expected one control for {criteria}, found {len(controls)}"
        )
    control = controls[0]
    if not control.is_visible() or not control.is_enabled():
        raise RuntimeError(f"Control not ready: {criteria}")
    return control


def owned_window(state: dict[str, Any]) -> Any:
    desktop = importlib.import_module("pywinauto").Desktop(backend="uia")
    window = desktop.window(
        handle=state["notepad_handle"],
        process=state["notepad_pid"],
        class_name="Notepad",
    ).wrapper_object()
    if not window.is_visible():
        raise RuntimeError("Run-owned Notepad is not visible")
    return window


def focus(window: Any) -> None:
    window.set_focus()
    win32gui = importlib.import_module("win32gui")
    wait_until(
        lambda: win32gui.GetForegroundWindow() == window.handle,
        "intended window focus",
    )


def start_notepad(state: dict[str, Any]) -> dict[str, Any]:
    app = importlib.import_module("pywinauto").Application(backend="uia")
    app.start("notepad.exe", wait_for_idle=False)
    state["notepad_pid"] = app.process
    window = app.window(class_name="Notepad")
    window.wait("visible enabled", timeout=4)
    state["notepad_handle"] = window.handle
    window = owned_window(state)
    focus(window)
    if unique(window, **EDITOR).get_value() != "":
        raise RuntimeError("New Notepad is not empty")
    return {"editor_selector": EDITOR, "fresh_empty_window": True}


def edit_notepad(state: dict[str, Any]) -> dict[str, Any]:
    editor = unique(owned_window(state), **EDITOR)
    editor.set_edit_text(FINAL_TEXT)
    wait_until(lambda: editor.get_value() == FINAL_TEXT, "exact three-line text")
    return {"exact_text_verified": True}


def move_notepad(state: dict[str, Any]) -> dict[str, Any]:
    window = owned_window(state)
    focus(window)
    if window.is_maximized():
        window.restore()
    titlebar = unique(window, control_type="TitleBar")
    rect = titlebar.rectangle()
    before = window.rectangle()
    target_left = 80 if abs(before.left - 40) <= 10 else 40
    target_top = max(40, before.top)
    # Use visible live title-bar geometry, even if remembered placement is offscreen.
    width = importlib.import_module("win32api").GetSystemMetrics(0)
    origin = (
        max(30, min((rect.left + rect.right) // 2, width - 150)),
        (rect.top + rect.bottom) // 2,
    )
    destination = (
        origin[0] + target_left - before.left,
        origin[1] + target_top - before.top,
    )
    titlebar.drag_mouse_input(src=origin, dst=destination, absolute=True)
    wait_until(
        lambda: abs(window.rectangle().left - target_left) <= 10,
        "title-bar move to left",
    )
    if window.rectangle().left == before.left:
        raise RuntimeError("Notepad did not move")
    if unique(window, **EDITOR).get_value() != FINAL_TEXT:
        raise RuntimeError("Text changed after title-bar drag")
    state["title_bar_drag_verified"] = True
    return {"title_bar_drag_verified": True, "window_left": window.rectangle().left}


def prepare_path(state: dict[str, Any]) -> dict[str, Any]:
    shell = importlib.import_module("win32com.shell.shell")
    constants = importlib.import_module("win32com.shell.shellcon")
    documents = Path(shell.SHGetFolderPath(0, constants.CSIDL_PERSONAL, None, 0))
    if not documents.is_dir():
        raise RuntimeError("Windows Documents folder does not exist")
    path = documents / f"cua-native-test-{datetime.now():%Y-%m-%d-%H%M%S-%f}.txt"
    if path.exists():
        raise FileExistsError("Refusing to overwrite existing output")
    state["saved_file_path"] = str(path)
    return {"saved_file_path": str(path), "output_did_not_exist": True}


def dialog(state: dict[str, Any], title: str) -> Any:
    gui = importlib.import_module("win32gui")
    matches: list[Any] = []

    def ready() -> bool:
        nonlocal matches
        # This host's UIA tree nests modal dialogs beneath their disabled owner;
        # Desktop.windows() enumerates roots and therefore cannot see them.
        matches = [
            child
            for child in owned_window(state).children(control_type="Window")
            if child.class_name() == "#32770" and child.window_text() == title
        ]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous {title} dialog")
        return len(matches) == 1 and matches[0].is_enabled()

    wait_until(ready, f"run-owned {title} dialog")
    result = matches[0]
    if gui.GetWindow(result.handle, 4) != state["notepad_handle"]:
        raise RuntimeError("Dialog owner is not the run-owned Notepad")
    return result


def open_save_as(state: dict[str, Any]) -> dict[str, Any]:
    focus(owned_window(state))
    importlib.import_module("pywinauto.keyboard").send_keys("^+s")
    window = dialog(state, "Save As")
    state["save_dialog_handle"] = window.handle
    return {"save_as_opened": True}


def configure_save(state: dict[str, Any]) -> dict[str, Any]:
    window = dialog(state, "Save As")
    filename = unique(window, auto_id="1001", control_type="Edit")
    filename.set_edit_text(state["saved_file_path"])
    encoding = unique(window, title="Encoding:", control_type="ComboBox")
    encoding.select("UTF-8")
    if filename.get_value() != state["saved_file_path"]:
        raise RuntimeError("Save filename did not match")
    if encoding.iface_value.CurrentValue != "UTF-8":
        raise RuntimeError("Save encoding is not UTF-8")
    return {"full_path_verified": True, "encoding_verified": "UTF-8"}


def save_document(state: dict[str, Any]) -> dict[str, Any]:
    window = dialog(state, "Save As")
    if Path(state["saved_file_path"]).exists():
        raise FileExistsError("Refusing to overwrite existing output")
    unique(window, auto_id="1", control_type="Button", title="Save").invoke()
    gui = importlib.import_module("win32gui")
    wait_until(
        lambda: not gui.IsWindow(state["save_dialog_handle"]),
        "Save As dismissal (never acknowledge overwrite)",
    )
    return verify_file(state)


def verify_file(state: dict[str, Any]) -> dict[str, Any]:
    path = Path(state["saved_file_path"])
    wait_until(path.is_file, "saved file")
    content = path.read_bytes()
    # UTF-8 permits a BOM; no whitespace/line normalization hides text errors.
    if content.decode("utf-8-sig") != FINAL_TEXT:
        raise RuntimeError("Saved UTF-8 file does not match exact document text")
    state["file_sha256"] = hashlib.sha256(content).hexdigest()
    return {
        "saved_file_path": str(path),
        "file_sha256": state["file_sha256"],
        "utf8_exact_file_verified": True,
    }


def close_created_notepad(state: dict[str, Any]) -> dict[str, Any]:
    verify_file(state)
    window = owned_window(state)
    if unique(window, **EDITOR).get_value() != FINAL_TEXT:
        raise RuntimeError("Document changed before close")
    old_pid = state["notepad_pid"]
    # Check process exit rather than HWND reuse or closing any other window.
    api = importlib.import_module("win32api")
    process = api.OpenProcess(0x100000, False, old_pid)
    try:
        window.close()
        event = importlib.import_module("win32event")
        wait_until(
            lambda: event.WaitForSingleObject(process, 0) == 0,
            "original Notepad process exit",
        )
    finally:
        process.Close()
    state["original_notepad_closed"] = True
    return {"only_created_notepad_closed": True}


def start_reopen_notepad(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("original_notepad_closed"):
        raise RuntimeError("Original Notepad closure was not confirmed")
    return start_notepad(state)


def open_file_dialog(state: dict[str, Any]) -> dict[str, Any]:
    focus(owned_window(state))
    importlib.import_module("pywinauto.keyboard").send_keys("^o")
    window = dialog(state, "Open")
    state["open_dialog_handle"] = window.handle
    filename = unique(window, auto_id="1148", control_type="Edit")
    filename.set_edit_text(state["saved_file_path"])
    if filename.get_value() != state["saved_file_path"]:
        raise RuntimeError("Open filename did not match")
    return {"open_dialog_full_path_verified": True}


def reopen_document(state: dict[str, Any]) -> dict[str, Any]:
    window = dialog(state, "Open")
    unique(window, auto_id="1", control_type="Button", title="Open").invoke()
    gui = importlib.import_module("win32gui")
    wait_until(
        lambda: not gui.IsWindow(state["open_dialog_handle"]), "Open dialog dismissal"
    )
    editor = unique(owned_window(state), **EDITOR)
    wait_until(lambda: editor.get_value() == FINAL_TEXT, "exact reopened document")
    return {"reopened_exact_text_verified": True}


def verify(state: dict[str, Any]) -> dict[str, Any]:
    window = owned_window(state)
    if unique(window, **EDITOR).get_value() != FINAL_TEXT:
        raise RuntimeError("Reopened document does not match")
    prior_hash = state["file_sha256"]
    result = verify_file(state)
    if state["file_sha256"] != prior_hash:
        raise RuntimeError("Saved file changed after reopening")
    if not state.get("title_bar_drag_verified") or not state.get(
        "original_notepad_closed"
    ):
        raise RuntimeError("Required movement/closure was not confirmed")
    if Path(state["saved_file_path"]).stem + " - Notepad" != window.window_text():
        raise RuntimeError("Reopened document title does not identify saved file")
    focus(window)
    return {
        **result,
        "reopened_exact_text_verified": True,
        "notepad_line_count": 3,
        "terminal_assertion": (
            "Exact three-line UTF-8 file in Documents saved without overwrite; "
            "title-bar drag and original process closure verified; reopened "
            "via a fresh Notepad Open dialog with exact Unicode text."
        ),
    }


STEPS = {
    "start_notepad": start_notepad,
    "edit_notepad": edit_notepad,
    "move_notepad": move_notepad,
    "prepare_path": prepare_path,
    "open_save_as": open_save_as,
    "configure_save": configure_save,
    "save_document": save_document,
    "close_created_notepad": close_created_notepad,
    "start_reopen_notepad": start_reopen_notepad,
    "open_file_dialog": open_file_dialog,
    "reopen_document": reopen_document,
    "verify": verify,
}


def main() -> None:
    root = Path(os.environ["LOCALAPPDATA"]) / "cua-agent-kit" / "inspection"
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "deps"))
    request = json.loads(base64.b64decode(sys.argv[1], validate=True))
    state = request["state"]
    try:
        result = STEPS[request["step"]](state)
        print(json.dumps({"ok": True, "state": state, "result": result}))
    except Exception as error:
        # No automatic replay of a step that may already have performed input.
        print(
            json.dumps(
                {
                    "ok": False,
                    "state": state,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
