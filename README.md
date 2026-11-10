# CUA Agent Kit

CUA Agent Kit is a starter kit for automating browser and Windows workflows,
developed at CVS Health to reduce repetitive, screen-based work. It uses AI to
discover the steps, then code to repeat them.

First, an OpenAI computer-use agent follows a workflow written in plain language
and records screenshots, actions, targets, and traces. After successful runs, a
Codex skill uses that evidence to build or update a deterministic workflow that
runs without an LLM.

## Why this exists

At CVS Health, operational work such as sending documents, processing referrals,
and supporting specialist consults requires teams to move between applications,
find the right record, review information, and take the next action. Even where
APIs exist, they do not always cover every action available in an application.
This kit complements API-based integrations by automating that UI-driven work,
with applications beyond healthcare.

AI computer-use agents can figure out how to complete a workflow from
plain-language instructions. But discovering how to do something and doing it
repeatedly are different problems. Once a workflow is understood, asking a model
to reason through the same steps on every run adds inference cost and
variability to work that ordinary code can perform.

For workflows with reliable, repeatable steps, this kit turns successful runs
into Playwright or pywinauto code your team can inspect, maintain, and reuse
without an LLM. When a workflow breaks, Codex can use production traces to
diagnose the issue and update the deterministic code, enabling AI-assisted
maintenance with engineer review, testing, and verification.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Access to the target website (the local sample is included)
- An OPENAI_API_KEY key for discovery

## Shared Setup

Clone the repository, install the Python dependencies, configure a model API
key, and put your workflow instructions in `prompt.py`.

```bash
git clone https://github.com/cvs-health/cua-agent-kit.git
cd cua-agent-kit
uv sync
```

Set `OPENAI_API_KEY` for AI discovery. Optionally set `OPENAI_BASE_URL` to use a
custom API endpoint. Deterministic runs do not require either variable.

## Browser

Discover workflows in a browser, then codify them into deterministic Playwright
code. The included browser example uses the local Care Intake sample app.

### Set up

Install Chromium:

```bash
uv run playwright install chromium
```

Configure your environment or `.env` for the target website. For the included
sample:

```dotenv
DISCOVERY_BACKEND=browser
START_URL=http://127.0.0.1:8081
WORKFLOW_ACCOUNT_JSON='{"username":"demo","password":"demo-password"}'
```

Start the sample app in a separate terminal:

```bash
uv run python sample_app/app.py
```

Open http://127.0.0.1:8081. For your own website, set `START_URL` and describe
its workflow and login in the prompt instead.

### Discover

Edit the instructions in
[`src/cua_agent_kit/discovery/prompt.py`](src/cua_agent_kit/discovery/prompt.py),
then run:

```bash
uv run cua-agent-discover
```

The browser is visible by default. Verify the result and repeat discovery as
needed until the workflow succeeds consistently. Recordings are saved under
`artifacts/discovery/<run-id>/`, with screenshots, `events.jsonl`, `run.json`,
and a Playwright `trace.zip`.

### Codify

From the repository root, ask Codex:

```text
Use $codify-playwright-workflow to codify the successful discovery runs.
```

The [browser skill](.codex/skills/codify-playwright-workflow/SKILL.md) uses the
recordings to build or update Playwright code with semantic locators rather than
replaying screen coordinates.

### Run

```bash
uv run cua-agent-run
```

The codified workflow runs without model calls or an API key. Its evidence is
saved under `artifacts/deterministic/<run-id>/`.

## Windows

Discover workflows on a remote Windows desktop, then codify accessible
application controls into deterministic pywinauto code. The included Windows
example saves a Unicode document in Notepad and reopens it, verifying both the
saved file and editor contents.

### Set up

Follow the [Windows VM setup guide](docs/windows-vm-setup.md) to install the
server and native dependencies with `windows-host/install.ps1`, then launch the
server with `windows-host/start.ps1` in the intended user's desktop session.
Keep the desktop unlocked and avoid competing input during automation.

The controller must be able to reach the VM's private address and server port.
Configure your local environment or `.env`:

```dotenv
DISCOVERY_BACKEND=windows
WINDOWS_HOST=YOUR_PRIVATE_VM_ADDRESS
WINDOWS_PORT=8000
```

Windows discovery uses the shared `OPENAI_API_KEY`. Model calls run on the
controller; application input and screenshots happen on the VM.

### Discover

Edit the Windows task in
[`src/cua_agent_kit/discovery/prompt.py`](src/cua_agent_kit/discovery/prompt.py),
then run:

```bash
uv run cua-agent-discover
```

Verify the outcome and repeat as needed. Recordings are saved under
`artifacts/discovery/<run-id>/`, with screenshots, `events.jsonl`, and
`run.json`. Windows recordings include available UIA/Win32 control metadata.

### Codify

From the repository root, ask Codex:

```text
Use $codify-windows-workflow to codify the successful discovery runs.
```

The [Windows skill](.codex/skills/codify-windows-workflow/SKILL.md) uses the
recordings to validate native selectors, implement pywinauto steps, and verify
replay on the VM.

### Run

With the same VM address and port settings:

```bash
uv run cua-agent-run-windows
```

The controller copies `src/cua_agent_kit/workflows/windows_steps.py` to the VM
and executes it through `computer_server`. No model calls or API key are needed.
Checkpoints and terminal assertions are saved under
`artifacts/deterministic/<run-id>/`.

### Run the Windows controller with Docker

After completing the Windows setup above, use Docker Compose instead of local
`uv` commands:

```bash
docker compose run --build --rm windows
```

This runs the deterministic Windows workflow once, writes audit records to
PostgreSQL, and keeps artifacts locally. For discovery, use
`docker compose run --build --rm windows cua-agent-discover`, then follow the
codification steps above.

The controller runs in the same Linux image used for browser workflows. The
target applications, `computer_server`, and pywinauto remain on the Windows VM,
which must be reachable from the container.

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
