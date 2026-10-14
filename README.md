# SAP Engineering Studio — RAG V1

A local SAP Integration Suite engineering workbench. Describe a supported
integration, retrieve scoped knowledge, inspect a semantic plan, execute it in a
fresh simulator, and retain independently verified trajectories as knowledge.
The SAP DEV workflow imports an approved exported iFlow, uploads and deploys it,
sends a controlled test, and verifies the exact fresh message log. Its tenant
acceptance remains unvalidated; see the [live workflow guide](docs/LIVE_WORKFLOW.md).
**No fine-tuning or 7B model is required.**

`Finetune` preserves the previous implementation. `RAG` contains this application.

## Run

Python 3.11 or 3.12, PostgreSQL 17 with pgvector, and ~600 MB for CPU retrieval
models are needed. A GPU is not needed. The first initialization downloads text
embedding and reranking assets; visual retrieval downloads its model when used.

```sh
python -m pip install uv==0.12.23
uv sync --frozen --extra dev
cp .env.example .env
# Configure SAP_CUA_DATABASE_URL for your local PostgreSQL database.
uv run sap-cua serve --port 8765
```

Open http://127.0.0.1:8765. The connection panel accepts session-only DEV credentials;
read-only readiness checks are also available through `sap-cua sap probe`.
Database and CPU-model initialization and seed indexing run in the background.
The setup UI remains accessible if retrieval is unavailable. `sap-cua rag init`
is also available for explicit initialization. The local CLI reads `.env`.
Keep database passwords URL-encoded in the DSN and never commit populated secrets.

Docker alternative: set `SAP_CUA_DB_PASSWORD` to a URL-safe random value in `.env`,
then `docker compose up --build`. The workbench listens on localhost:8000; the
database has no published host port. Knowledge initialization runs after the UI starts.
The local desktop setup was tested natively; Compose integration is supplied for
portability, with separate database and container-startup checks in CI.

## Examples

- Create HTTPS → Content Modifier → Router → OData V4 with error handling.
- Create SFTP to OData V4 integration.
- Diagnose a failing flow with HTTP 401.

The planner is a conservative deterministic compiler for [supported patterns](docs/PLANNER_SUPPORTED_INTENTS.md).
Diagnostics are not automatic repairs. Unsupported mapping/code/ProcessDirect
requirements remain blocked. Sandbox results do not prove that SAP accepted an
artifact or that an external business transaction succeeded.

```sh
uv run sap-cua rag search "OData HTTP 401 OAuth credentials"
uv run sap-cua rag run "Create HTTPS Content Modifier Router to OData V4"
uv run sap-cua rag ingest approved-knowledge.jsonl
uv run sap-cua rag benchmark
uv run pytest -q
```

## Workspace features

Add approved text directly from the Knowledge panel, filter searches by collection,
reopen saved plans after refresh, and download sanitized run evidence. See the
[workspace guide](docs/WORKSPACE_FEATURES.md) for versioning and execution boundaries.

## SAP DEV workflow

Configure management and separate runtime OAuth credentials, enable DEV writes,
import a reviewed UTF-8 iFlow export, set a synthetic POST/response contract,
review the rendered ZIP and start the job. History, cancellation and evidence
downloads remain available after a browser refresh. Existing iFlows are not
overwritten and uncertain writes are not retried. Follow the
[complete workflow and export requirements](docs/LIVE_WORKFLOW.md).

## Implemented

- Strict knowledge schema, content hashes, embedding asset fingerprints, incremental
  versions and domain routing; PostgreSQL full-text/pgvector candidate fusion,
  CPU reranking, bounded context and source provenance.
- Trusted customer/tenant scope filters before retrieval; scoped run history,
  viewer/engineer/admin contracts; approved tenant naming and credential-alias facts.
- Typed semantic action arguments, dependency checks, budgets, atomic run claims,
  separate action and state verification, bounded transient sandbox recovery.
- Automatic sanitized successful-trajectory ingestion; scoped CLIP screenshot
  retrieval with approved capture, masking regions and metadata stripping.
- Capability-based hybrid router and optional OpenCUA provider/fallback interfaces.
  Paid provider calls require explicitly configured cost upper bounds.
- Existing SAP API client with OAuth, CSRF/cookie preflight, known resource paths,
  explicit mutation permission and no automatic retry of uncertain writes.
- Playwright origin isolation, dynamic DOM geometry and real pointer drag/drop;
  optional bounded vision escalation with a caller-owned action authorizer.
- Nine canonical pattern blueprints and a hash-approved exported-iFlow ZIP
  parameterizer with XML/XXE/path/size checks. Blueprints are not SAP-native exports.
- OpenTelemetry semantic action spans/counters, structured run evidence, local
  authenticated-session dashboard, 20-task simulator ablations and retrieval metrics.

## Boundaries

The dashboard includes both sandbox engineering plans and explicit approved-template
DEV deployments. Live execution requires a DEV connection, separate runtime OAuth
credentials, an approved exported iFlow and its functional test contract. The
workflow is covered by simulated API contracts and remains unvalidated against
the user's SAP tenant. Browser/GUI automation has separate provider interfaces;
real SAP DOM selectors and dialogs are not yet validated.

The included 38 notes are original engineering guidance, not a complete SAP
manual. Approved JSONL, text, Markdown, HTML and allowlisted public HTTPS sources
can be ingested through the ingestion library. Retrieved content never supplies
policy, code, credentials or executor selectors.

Local role and tenant scope come from trusted configuration, not request bodies.
This is not a hosted multiuser authentication system. Use a least-privilege DB role,
external identity provider, access audit and database row-level isolation before
commercial multiuser hosting. The local PostgreSQL developer role is for local use.

Screenshot masking covers supplied regions; arbitrary screen secrets require an
approved capture policy. No automatic claim of perfect visual redaction is made.
OTel instrumentation is active; attach a collector/exporter through the SDK for
centralized telemetry. Default metric snapshots are local and contain no task text.

See [audit](docs/EXISTING_IMPLEMENTATION_AUDIT.md), [status](docs/STATUS.md),
[roadmap](docs/ROADMAP.md), and [fine-tuning decision](docs/FINE_TUNING_DECISION.md).
