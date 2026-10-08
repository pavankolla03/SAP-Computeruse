# SAP Engineering Studio — RAG V1

A local SAP Integration Suite engineering workbench. Describe a supported
integration, retrieve scoped knowledge, inspect a semantic plan, execute it in a
fresh simulator, and retain independently verified trajectories as knowledge.
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
uv run sap-cua rag init
uv run sap-cua serve --port 8765
```

Open http://127.0.0.1:8765. `rag init` creates pgvector/schema and incrementally
indexes the included original engineering notes. The local CLI reads `.env`.
Keep database passwords URL-encoded in the DSN and never commit populated secrets.

Docker alternative: set `SAP_CUA_DB_PASSWORD` to a URL-safe random value in `.env`,
then `docker compose up --build`. The workbench listens on localhost:8000; the
database has no published host port. Compose initializes knowledge before serving.
The local desktop setup was tested natively; Compose integration is supplied for
portability, with separate database and container-startup checks in CI.

## Examples

- Create HTTPS → Content Modifier → Router → OData V4 with error handling.
- Create SFTP to OData V4 integration.
- Diagnose a failing flow with HTTP 401.

The planner is a conservative deterministic compiler for supported patterns.
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

The dashboard deliberately executes only the simulator. A real DEV tenant,
approved iFlow exports, tenant-specific selectors, capability/permission checks
and functional test contracts are required to enable live end-to-end execution.
API operations and the browser runtime are available as explicit integration
components; their live orchestration is not yet tenant validated.

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
