# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cua_agent_kit.clients.windows import inspection_probe as probe


def test_selector_candidates_do_not_use_handles_pids_or_truncated_names():
    control = {
        "automation_id": "15",
        "control_type": "Edit",
        "class_name": "Edit",
        "name": "truncated",
        "name_truncated": True,
        "native_handle": 12345,
        "process_id": 999,
    }
    assert probe.selector_candidates(control, "uia") == [
        {"auto_id": "15", "control_type": "Edit"},
        {"class_name": "Edit"},
    ]


def test_win32_edit_metadata_does_not_read_document_contents():
    info = Mock()
    info.class_name = "Edit"
    info.control_id = 15
    info.process_id = 100
    info.handle = 12345
    info.automation_id = ""
    info.control_type = ""
    info.enabled = True
    info.visible = True
    info.rectangle = SimpleNamespace(left=0, top=0, right=100, bottom=100)
    metadata = probe.control_metadata(SimpleNamespace(element_info=info), "win32")
    assert metadata["name"] is None
    assert {"control_id": 15} in metadata["selector_candidates"]


def test_control_tree_bound_reports_truncation_and_keeps_parent_links(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(probe, "MAX_TREE_CONTROLS", 3)
    monkeypatch.setattr(probe, "control_metadata", lambda node, _: {"name": node.name})
    leaves = [SimpleNamespace(name=str(i), children=lambda: []) for i in range(4)]
    root = SimpleNamespace(name="root", children=lambda: leaves)
    tree = probe.snapshot_tree(root, "uia")
    assert tree["truncated"] is True
    assert len(tree["controls"]) == 3
    assert [control["parent_index"] for control in tree["controls"]] == [None, 0, 0]


def test_backend_failure_preserves_other_backend_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    def inspect_backend(request, backend):
        if backend == "uia":
            raise RuntimeError("UIA provider unavailable")
        return {"control": {"control_id": 15}}

    monkeypatch.setattr(probe, "inspect_backend", inspect_backend)
    result = probe.inspect({"capture": "focus"})
    assert result["status"] == "partial"
    assert result["backends"] == {"win32": {"control": {"control_id": 15}}}
    assert result["errors"] == {"uia": "RuntimeError"}
