---
name: codify-windows-workflow
description: Convert verified Windows computer-use discovery recordings into deterministic pywinauto workflows, or update a native workflow after its prompt changes. Use recorded UIA/Win32 controls and screenshots to implement and verify accessible desktop automation. Not for browser Playwright workflows or opaque remote-rendered controls.
---

# Codify Windows Workflow

Turn verified discovery into source-controlled native automation that executes
in the application's Windows session without model calls.

## Repository entrypoints

Resolve these paths from the repository root:

- `src/cua_agent_kit/discovery/prompt.py`: current workflow intent.
- `artifacts/discovery/<run-id>/`: prompt/metadata in `run.json`, actions and native
  targets in `events.jsonl`, screenshots, and independent verification artifacts.
  Windows runs have no Playwright trace.
- `src/cua_agent_kit/clients/windows/inspection_probe.py`: native target schema
  and capture limits; `discovery/windows_computer.py` defines capture timing.
- `src/cua_agent_kit/workflows/windows_steps.py`: VM-side native example. Adapt
  these functions to the requested workflow rather than adding another agent loop.
- `src/cua_agent_kit/workflows/windows_runner.py`: controller deployment, bounded
  commands, checkpoints, and existing artifact/publication path.
- `uv run cua-agent-run-windows`: native replay; `cua-agent-run` stays browser-only.

## Verify the source workflow

Compare the current prompt with recorded prompts/hashes. Inspect action outcomes,
representative screenshots, and native targets. `completed` and a model success
summary are not correctness assertions. Require actual endpoint evidence: exact
control values, console output, an exported file, or another appropriate check.
If missing, verify read-only when possible or discover within the authorized scope.
Do not silently select a successful older run whose prompt no longer matches.

Typed action text is redacted. Recover intended inputs from the prompt or an
authorized configuration source, not `[REDACTED]`. Keep real run IDs, host addresses,
credentials, and raw control dumps out of committed code and skill instructions.

## Translate actions into scoped native operations

Inspect `Action.target.backends.uia`/`.win32`: control, ancestors, window,
patterns, selector candidates, and truncation/errors. Candidates are observed
criteria, not certified unique/stable selectors. UIA/Win32 focus can differ;
partial evidence does not establish that the whole application is inaccessible.

Scope each lookup to the intended window/process and verify uniqueness live.
Prefer automation IDs plus control types, scoped names, or Win32 control IDs.
Titles can change after editing. Never reuse recorded handles, PIDs, bounds, or
traversal positions as repeat-run selectors. Fresh handles obtained for run-owned
windows are valid runtime scope. Console UIA process identity can belong to the
console host, not PowerShell: establish a run-owned window identity.

Use supported native patterns for input and assertions. `window_text()` may be
an accessible label, not document contents; read Value/Text patterns instead.
A console may expose readable Text but no writable Value. Use the existing host
`keyboard_input.type_literal` after validating selector and foreground focus;
legacy consoles can drop shifted characters from CUA's Unicode injection.
Console Text can include cell-padding spaces: normalize presentation padding
when checking exact output lines, without accepting just an echoed command.

Preserve outcomes and explicitly requested interaction techniques. Remove
exploratory clicks and redundant screenshots; native launch can replace launch
navigation. Derive a requested title-bar drag from the live title-bar geometry,
not recorded coordinates. For Alt+Tab, assert the resulting foreground window;
do not mask a failed switch with a fallback focus call.

## Execute and validate

Keep Windows-only imports in the VM path so controller modules import on Mac/Linux.
Native dependencies live under `%LOCALAPPDATA%\cua-agent-kit\inspection\deps`.
Discovery deploys helper sources, not dependencies. Use the existing CUA command
API, not another listener. Host/IP/port belong in config; workflow inputs and
steps belong in code. Do not introduce CLI parsing or model calls.

Keep each step bounded below the 12-second host command timeout. Poll read-only
observable conditions rather than long fixed sleeps. Stop on failed assertions
or ambiguous acknowledgements; never automatically replay input that may already
have happened. Preserve checkpoint diagnostics and report the last confirmed step.
Do not close unrelated windows or edit existing documents to reset a test.

Verify in fresh run-owned windows, not only against discovery's handles. Assert
the exact terminal state independently of screenshots. Repeat when needed to
establish fresh-instance targeting or after a meaningful fix. One environment's
success does not prove cross-version/language/DPI compatibility. Run relevant
checks for material changes. Report invocation, evidence, actual replay results,
and unverified behavior. When the prompt changes, update steps and assertions
together; do not label stale code as matching new intent.
