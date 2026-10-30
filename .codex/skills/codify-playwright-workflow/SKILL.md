---
name: codify-playwright-workflow
description: Convert successful AI computer-use runs into deterministic Playwright workflows, or update an existing deterministic workflow after its natural-language prompt changes. Use when Codex needs to inspect CUA logs, screenshots, Playwright traces, or recorded DOM targets; implement stable locator-based automation; reconcile prompt changes with prior successful runs; or verify that deterministic automation still matches the demonstrated workflow.
---

# Codify Playwright Workflow

Turn demonstrated browser behavior into plain Playwright code that runs without an
LLM. Treat successful discovery runs as evidence, not as executable specifications.

## Gather evidence

1. Locate the authoritative workflow prompt, deterministic workflow, and discovery
   artifacts. Prefer `src/cua_agent_kit/discovery/prompt.py` for the prompt,
   `src/cua_agent_kit/workflows/` for deterministic orchestration, and
   `artifacts/discovery/<run-id>/` for run evidence (or the configured `ARTIFACTS_DIR`).
2. Read `references/discovery-artifacts.md` before evaluating recorded runs.
3. Use only runs that reached the prompt's intended terminal state. Verify success
   from the final screenshot, URL, recorded assertion, or other observable evidence;
   do not trust a success message alone.
4. Prefer multiple successful runs. Compare them to distinguish required steps from
   incidental waits, coordinates, focus changes, and recovery behavior.
5. Use runs captured with the current viewport and environment. Exclude incompatible
   runs unless they are intentionally being used to validate responsive behavior.

If the available evidence cannot establish a stable target or outcome, state the
missing evidence and request another discovery run. Do not invent selectors.

## Translate the workflow

1. Build a short action inventory that maps each prompt step to observed evidence.
2. Replace coordinate actions with stable Playwright locators. Prefer, in order:
   exact role and accessible name, label, test ID, placeholder, stable text, stable
   ID, and scoped CSS as a last resort.
3. Account explicitly for frames, popups, post-login screens, loading states, and
   alternate states observed across successful runs.
4. Use observable state transitions instead of fixed sleeps. Wait for the next
   required control or terminal state.
5. Codify login along with the workflow; consumers need no setup hook before
   discovery. The Python prompt interpolates environment-backed credentials for model
   input, while evidence saves a credential-redacted prompt. Read
   credentials from configuration in deterministic login code, not source literals.
   A codified login tool may later reduce discovery tokens but is optional.
6. Keep the deterministic implementation independent of `openai-agents`. Share
   configuration or browser utilities only when that does not couple it to the agent.
7. Separate screen-specific interactions from workflow orchestration when the flow
   contains more than a few actions or will be extended later.
8. Reuse the repository's `RunArtifacts` recorder in deterministic workflows. Capture
   a screenshot after every semantic step, on failure, and at the terminal state, and
   retain a Playwright trace for diagnosis.

## Update after a prompt change

1. Compare the current prompt with the prompt represented by the last codified
   successful run. Use version control when available.
2. Identify added, removed, reordered, and changed outcomes before editing code.
3. Inspect successful runs produced from the new prompt. New evidence supersedes old
   evidence only for the changed steps.
4. Preserve deterministic behavior outside the demonstrated change.
5. Remove obsolete steps and their now-unused locators, while retaining recovery
   handling still supported by current successful runs.

## Verify

1. Run formatting, linting, and type checks configured by the repository.
2. Run focused offline tests for locator construction and workflow branching when
   available.
3. Run the deterministic workflow against the same test environment when authorized.
   Stop at exactly the terminal state described by the prompt and avoid unrelated
   records or mutations.
4. On failure, capture a Playwright trace and screenshot. Fix the semantic locator or
   state transition rather than adding coordinate clicks or arbitrary delays.
5. Report which successful run artifacts support the implementation, what changed,
   verification performed, and any unresolved variability.
6. Report the compatible source run IDs, implementation paths, terminal assertion,
   and successful deterministic verification run ID in the user-facing update or
   final handoff only. These IDs refer to local runs on the developer's machine;
   do not add them to commit messages, workflow code, comments, runtime events,
   or repository metadata files. Keep run artifacts focused on evidence from
   their own execution.
