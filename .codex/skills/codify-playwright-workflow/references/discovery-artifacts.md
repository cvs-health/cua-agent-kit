# Discovery artifact contract

Use this contract when reading existing discovery runs or designing the recorder that
produces them. A run should be self-contained under:

```text
artifacts/discovery/<run-id>/
├── run.json
├── events.jsonl
├── trace.zip
└── screenshots/
```

## Required evidence

The artifact root can be overridden with `ARTIFACTS_DIR`. Each repository owns one
workflow; there is no named-workflow subdirectory.

Schema-v2 `run.json` contains `schema_version`, `run_id`, the exact `prompt`,
`prompt_sha256`, `started_at`, and `status`. Once browser capture starts, it also
records `start_url` and `viewport`. Finalization adds `completed_at`, `final_url`,
`terminal_assertion`, `screenshot_count`, and `event_count`. `error` and `trace_error`
are included when applicable. Interrupted runs may lack finalization fields.

Workflow names, application versions, and Git commits are not recorded by this
schema. Do not reject runs for lacking them. Compare the recorded prompt and hash
with the current prompt when selecting evidence. Older schema-v1 artifacts may
retain named-workflow metadata and directories; inspect their schema and prompt
before using them rather than assuming they match the current workflow.

`events.jsonl` contains ordered records with:

- `sequence` and `timestamp`;
- `action`, `outcome`, and action-specific `details`;
- `url` for the page;
- `screenshot`, a run-relative path or null when no screenshot was captured;
- `target`, DOM metadata when available, or null for actions without a target.

Pointer actions capture the target under the pointer; typing and keypress actions
capture the focused target. Frame URL and name are stored inside target metadata
when available, not as required top-level event fields. Capture failures can leave
missing screenshots or target metadata; use other evidence when sufficient.

Useful target metadata includes tag, role, accessible name, label, placeholder,
test ID, stable ID, visible text, frame chain, and candidate locator. Coordinates may
be retained for diagnosis but are never sufficient for deterministic automation.

Use Playwright tracing with screenshots and DOM snapshots when possible. The semantic
event journal remains necessary because it connects each CUA action to the target that
was under the pointer or held focus at execution time.

## Successful-run criteria

A run is successful only when observable evidence proves the requested terminal state.
Discovery records `completed` when the agent finishes and leaves `terminal_assertion`
null. Neither proves workflow success: review the screenshots, events, and trace
against the recorded prompt. Do not require a discovery assertion that the recorder
does not produce or rely only on the model's final message.

Deterministic runs record `succeeded` only after their verification completes, with
a descriptive terminal assertion such as `sample_appointment_verified`. This string reports
the verified outcome; it does not perform the check itself. Keep failed runs for
debugging, but never use them as the primary codification source. `trace.zip` may be
absent when tracing fails; inspect recorded errors and available evidence.

## Sensitive data

Redact passwords, usernames when required, tokens, API keys, PHI, and form contents
before writing artifacts. For typing actions, record a semantic marker such as
`credential:password` instead of the value. Screenshots and Playwright traces may also
contain sensitive data; store them only in an approved local location, keep them out
of version control, and apply the repository's retention policy.
