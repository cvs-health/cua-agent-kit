# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

"""Read-only UIA/Win32 probe executed in the Windows desktop session.

This file is copied to the host by WindowsClient. Windows-only libraries are
loaded at runtime so the controller package remains importable on other OSes.
The command argument is a base64-encoded JSON request, not workflow instructions.
"""

import base64
import importlib
import json
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

TARGET_SCHEMA_VERSION = 1
MAX_ANCESTORS = 12
MAX_TREE_CONTROLS = 100
MAX_TREE_DEPTH = 5
PATTERNS = (
    "Invoke",
    "Value",
    "Text",
    "RangeValue",
    "Selection",
    "SelectionItem",
    "Toggle",
    "ExpandCollapse",
    "Scroll",
    "Window",
)


def selector_candidates(control: dict[str, Any], backend: str) -> list[dict[str, Any]]:
    """Return observed lookup criteria, never asserted-unique selectors."""
    candidates: list[dict[str, Any]] = []
    control_type = control.get("control_type")
    if backend == "uia" and control.get("automation_id"):
        candidate = {"auto_id": control["automation_id"]}
        if control_type:
            candidate["control_type"] = control_type
        candidates.append(candidate)
    if backend == "win32" and control.get("control_id") not in {None, 0, -1}:
        candidates.append({"control_id": control["control_id"]})
    if control.get("name") and not control.get("name_truncated"):
        candidate = {"title": control["name"]}
        if backend == "uia" and control_type:
            candidate["control_type"] = control_type
        elif control.get("class_name"):
            candidate["class_name"] = control["class_name"]
        candidates.append(candidate)
    if control.get("class_name"):
        candidates.append({"class_name": control["class_name"]})
    return candidates


def control_metadata(wrapper: Any, backend: str) -> dict[str, Any]:
    info = wrapper.element_info
    rect = info.rectangle
    class_name = info.class_name
    is_password = False
    if backend == "uia":
        is_password = bool(info.element.CurrentIsPassword)
    # Win32 Edit window text can be document/form contents rather than a label.
    omit_name = is_password or (
        backend == "win32"
        and (class_name.lower() == "edit" or "richedit" in class_name.lower())
    )
    name = None if omit_name else info.name
    data = {
        "name": name[:200] if name else None,
        "name_truncated": bool(name and len(name) > 200),
        "class_name": class_name,
        "control_type": getattr(info, "control_type", None),
        "automation_id": getattr(info, "automation_id", None),
        "control_id": info.control_id,
        "process_id": info.process_id,
        "native_handle": info.handle,
        "enabled": bool(info.enabled),
        "visible": bool(info.visible),
        "bounds": {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
        },
    }
    if backend == "uia":
        data["framework_id"] = info.framework_id
        data["is_password"] = is_password
        uia = importlib.import_module("pywinauto.uia_defines").IUIA()
        patterns = []
        for pattern in PATTERNS:
            property_id = getattr(
                uia.UIA_dll, f"UIA_Is{pattern}PatternAvailablePropertyId"
            )
            if info.element.GetCurrentPropertyValue(property_id):
                patterns.append(pattern)
        data["patterns"] = patterns
    data["selector_candidates"] = selector_candidates(data, backend)
    return data


def snapshot_tree(root: Any, backend: str) -> dict[str, Any]:
    """Bounded foreground tree; expose truncation rather than claiming completeness."""
    controls: list[dict[str, Any]] = []
    pending = [(root, None, 0)]
    truncated = False
    errors: list[str] = []
    while pending and len(controls) < MAX_TREE_CONTROLS:
        wrapper, parent_index, depth = pending.pop(0)
        try:
            metadata = control_metadata(wrapper, backend)
            index = len(controls)
            controls.append(
                {
                    "index": index,
                    "parent_index": parent_index,
                    "depth": depth,
                    **metadata,
                }
            )
            children = wrapper.children()
            if depth >= MAX_TREE_DEPTH:
                truncated = truncated or bool(children)
            else:
                room = MAX_TREE_CONTROLS - len(controls) - len(pending)
                truncated = truncated or len(children) > room
                pending.extend((child, index, depth + 1) for child in children[:room])
        except Exception as error:
            errors.append(type(error).__name__)
    return {
        "controls": controls,
        "truncated": truncated or bool(pending),
        "errors": errors,
        "max_controls": MAX_TREE_CONTROLS,
        "max_depth": MAX_TREE_DEPTH,
    }


def inspect_backend(request: dict[str, Any], backend: str) -> dict[str, Any]:
    desktop = importlib.import_module("pywinauto").Desktop(backend=backend)
    if request["capture"] == "point":
        wrapper = desktop.from_point(request["x"], request["y"])
    elif backend == "uia":
        uia = importlib.import_module("pywinauto.uia_defines").IUIA()
        element_info = importlib.import_module(
            "pywinauto.uia_element_info"
        ).UIAElementInfo
        wrapper_class = importlib.import_module(
            "pywinauto.controls.uiawrapper"
        ).UIAWrapper
        element = uia.get_focused_element()
        if not element:
            raise RuntimeError("No focused UIA control")
        wrapper = wrapper_class(element_info(element))
    else:
        hwnd = importlib.import_module("win32gui").GetForegroundWindow()
        wrapper_class = importlib.import_module(
            "pywinauto.controls.hwndwrapper"
        ).HwndWrapper
        wrapper = wrapper_class(hwnd).get_focus()
        if wrapper is None:
            raise RuntimeError("No focused Win32 control")

    ancestors = []
    parent = wrapper.parent()
    while parent is not None and len(ancestors) < MAX_ANCESTORS:
        ancestors.append(control_metadata(parent, backend))
        parent = parent.parent()
    result = {
        "control": control_metadata(wrapper, backend),
        "ancestors": ancestors,
        "ancestors_truncated": parent is not None,
        "window": control_metadata(wrapper.top_level_parent(), backend),
    }
    if request.get("include_tree"):
        # The foreground window, not necessarily the point target's window.
        hwnd = importlib.import_module("win32gui").GetForegroundWindow()
        window = desktop.window(handle=hwnd).wrapper_object()
        result["foreground_tree"] = snapshot_tree(window, backend)
    return result


def inspect(request: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": "windows-controls",
        "schema_version": TARGET_SCHEMA_VERSION,
        "capture": request["capture"],
        "captured_at": datetime.now(UTC).isoformat(),
        "backends": {},
        "errors": {},
    }
    for backend in ("uia", "win32"):
        try:
            result["backends"][backend] = inspect_backend(request, backend)
        except Exception as error:
            result["errors"][backend] = type(error).__name__
    result["status"] = (
        "ok"
        if len(result["backends"]) == 2
        else "partial"
        if result["backends"]
        else "unavailable"
    )
    return result


def main() -> None:
    dependencies = (
        Path(os.environ["LOCALAPPDATA"]) / "cua-agent-kit" / "inspection" / "deps"
    )
    sys.path.insert(0, str(dependencies))
    request = json.loads(base64.b64decode(sys.argv[1], validate=True))
    if request["capture"] == "capabilities":
        try:
            importlib.import_module("pywinauto")
            result = {"available": True, "pywinauto_version": version("pywinauto")}
        except ImportError as error:
            result = {"available": False, "error_type": type(error).__name__}
    else:
        result = inspect(request)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
