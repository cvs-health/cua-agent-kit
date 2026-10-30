-- SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE workflow_runs (
    run_id TEXT PRIMARY KEY,
    execution_mode TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    finished_at TIMESTAMPTZ,
    terminal_assertion TEXT,
    error TEXT,
    storage_backend TEXT,
    storage_namespace TEXT,
    storage_prefix TEXT,
    upload_error TEXT
);
CREATE INDEX workflow_runs_started_at_idx ON workflow_runs (started_at);
