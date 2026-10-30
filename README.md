# CUA Agent Kit

CUA Agent Kit turns AI-driven browser workflows into reliable, low-cost
Playwright automation. First, an OpenAI computer-use agent follows a workflow
written in plain language and records screenshots, browser actions, DOM targets,
and a Playwright trace. After successful runs, Codex uses that evidence to build
or update a deterministic workflow that runs without an LLM.

This kit targets workflows accessed directly through a web browser, not
applications running in remote desktop environments.

Use this repository as a starter for your team's workflow. The default discovery
prompt and deterministic runner log in to the local Care Intake sample app, find
a fictional referral, schedule an appointment, and verify confirmation.

## Why this exists

Many workflows still require interacting with a UI where APIs are not available.
This kit complements API-based integrations by automating that browser-based
work.

AI computer-use agents can figure out how to complete a browser workflow from
plain-language instructions. But discovering how to do something and doing it
repeatedly are different problems. Once a workflow is understood, asking a model
to reason through the same steps on every run adds inference cost and
variability to work that ordinary code can perform.

This kit uses AI to discover browser workflows, then turns successful runs into
Playwright code your team can inspect, maintain, and reuse without an LLM.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Access to the target website (the local sample is included)
- An OPENAI_API_KEY key for discovery

## Setup

Clone the repository, then install the Python dependencies and Chromium:

```bash
git clone https://github.com/cvs-health/cua-agent-kit.git
cd cua-agent-kit
uv sync
uv run playwright install chromium
```

Set `OPENAI_API_KEY` for AI discovery. Optionally set `OPENAI_BASE_URL` to use a
custom API endpoint. Deterministic runs do not require either variable.

Set `START_URL` and `WORKFLOW_ACCOUNT_JSON` for your target website and account.
The included sample uses these defaults:

```dotenv
START_URL=http://127.0.0.1:8081
WORKFLOW_ACCOUNT_JSON='{"username":"demo","password":"demo-password"}'
```

Start the sample app in a separate terminal:

```bash
uv run python sample_app/app.py
```

Open http://127.0.0.1:8081.

## Discover a workflow with AI

The workflow instructions are in
[`src/cua_agent_kit/discovery/prompt.py`](src/cua_agent_kit/discovery/prompt.py).
Edit that file, then run:

```bash
uv run cua-agent-discover
```

The browser is visible by default so you can watch the agent. Run it several
times and change the prompt as needed until the workflow succeeds consistently.
Evidence is saved under:

```text
artifacts/discovery/<run-id>/
```

Each run includes screenshots, `events.jsonl`, `run.json`, and `trace.zip`.

## Codify a successful workflow

From the repository root, ask Codex:

```text
Use $codify-playwright-workflow to codify the successful discovery runs.
```

Codex compares the successful runs and updates the deterministic Playwright code
using stable semantic locators instead of recorded screen coordinates.

## Run the deterministic workflow

```bash
uv run cua-agent-run
```

This path uses Playwright directly and does not call an LLM. Its evidence is
saved under:

```text
artifacts/deterministic/<run-id>/
```

## Change the workflow

1. Edit `src/cua_agent_kit/discovery/prompt.py`. For a new website, also set
   `START_URL` and describe login using `{username}` and `{password}`.
   Credentials from `WORKFLOW_ACCOUNT_JSON` are injected at runtime and sent to
   the model. See [Security and sensitive data](#security-and-sensitive-data)
   before using real credentials. No setup code is needed before discovery.
   Codification creates deterministic login in `workflows/setup.py` and workflow
   steps in `workflows/steps.py`.
2. Run `uv run cua-agent-discover` until the changed workflow succeeds
   consistently.
3. Ask Codex to codify the successful runs again.
4. Run `uv run cua-agent-run` to verify the deterministic version.

## Run persistence

By default, the app does not write to a database or upload the run directory to
object storage. Run artifacts stay in local directories under `artifacts/`
(`DATABASE_BACKEND=none`, `OBJECT_STORAGE_BACKEND=local`).

You can independently enable PostgreSQL for run audit records and Azure Blob
Storage for artifacts.

### PostgreSQL

Set the following environment variables to enable PostgreSQL:

```dotenv
DATABASE_BACKEND=postgres
DATABASE_JDBC_URI=jdbc:postgresql://localhost:5432/cua_agent
DATABASE_USER=cua
```

The application container runs Flyway migrations before starting a workflow.
Direct `uv` runs require the schema to have been migrated first. Versioned
migrations live in [`flyway/sql`](flyway/sql); add new versions rather than
editing applied migrations.

### Azure Blob Storage

Set the following environment variables to enable Azure Blob Storage:

```dotenv
OBJECT_STORAGE_BACKEND=azure
AZURE_STORAGE_ACCOUNT_URL=https://YOUR_ACCOUNT.blob.core.windows.net
AZURE_STORAGE_CONTAINER=YOUR_CONTAINER
```

Create the container beforehand. Authentication uses `DefaultAzureCredential`
(for example, Azure CLI login locally or managed identity in deployment), with
blob write access. Artifacts are uploaded under `<run-id>/`; local copies remain
available.

### Other backends

To add another database or object store, implement the
[`DatabaseClient`](src/cua_agent_kit/clients/database/database.py) or
[`ObjectStorageClient`](src/cua_agent_kit/clients/object_storage/object_storage.py)
interface.

### Local PostgreSQL with Compose

Compose includes PostgreSQL and the sample app for local development:

```bash
docker compose up -d --wait postgres sample-app
docker compose run --build --rm app
```

This runs the deterministic workflow once, writes audit records to PostgreSQL,
and keeps artifacts locally. For discovery, use
`docker compose run --build --rm app cua-agent-discover`.

## Security and sensitive data

### Data sent to the model

Discovery sends the workflow prompt, including credentials from
`WORKFLOW_ACCOUNT_JSON`, plus browser screenshots and action history to the
configured model endpoint. Use an endpoint approved for the data involved and
review its retention policies, including those of any gateway configured by
`OPENAI_BASE_URL`.

### Evidence retained and redaction limits

Treat run artifacts and logs as sensitive, not as sanitized exports.

Both discovery and deterministic runs record evidence. `trace.zip` can contain
action arguments, credentials, cookies or session tokens, network requests and
responses, DOM snapshots, and source files. Screenshots capture visible data;
`run.json` includes the workflow prompt, URLs, and errors; `events.jsonl`
includes URLs and DOM target text.

Credential replacement in selected text fields and the `[REDACTED]` marker for
discovery typing events are best-effort protections, not comprehensive redaction
of JSON fields, screenshots, traces, or logs.

### Protecting credentials and evidence

For accounts whose credentials must not reach the model, adapt discovery to
authenticate in local code before the agent runs, or through a login tool that
reads credentials locally and executes the authentication steps.

Enabling a storage backend uploads the complete run directory without additional
redaction and leaves local copies in place. Restrict access to local and
uploaded evidence, use encrypted storage, and configure retention and deletion
for artifacts, logs, and database records. See
[Run persistence](#run-persistence) for storage configuration.

Do not commit artifacts or attach them to public issues. Review and sanitize
evidence before sharing it, including with an AI coding assistant for
codification.

## Development checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check
uv run ty check
```

Inspired by Kelsey Hightower's
[Zero Token Architecture talk](https://www.youtube.com/watch?v=A7WFt2JQ5sg) at
PlatformCon 2026.
