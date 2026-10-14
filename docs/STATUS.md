# RAG V1 status — 14 October 2026

Working local application; real SAP execution remains unvalidated.

| Area | Evidence | Remaining gate |
|---|---|---|
| Branch preservation | Finetune retains 325c654; development on RAG | None |
| Core/planner/dashboard | Browser requirement → sources → plan → verified run | General free-form planning and complex contracts |
| PostgreSQL/pgvector | Actual native PostgreSQL 17.11, pgvector 0.8.7; version/isolation checks pass | Production least-privilege role + RLS/IAM |
| Text RAG | Actual BGE + MiniLM; 38 original seed objects | Broader approved corpus, held-out evaluation |
| SAP API / live orchestration | Session or environment profiles; approved-template upload/deploy/test/MPL job; mocked HTTP contracts | DEV credentials, approved export and actual tenant acceptance |
| Playwright | Chromium dynamic pointer insertion and dashboard pass | Real SAP DOM selectors and dialogs |
| CUA | OpenCUA optional adapter + bounded fallback | Practical inference hardware/provider; held-out grounding |
| Trajectory memory | Verified sandbox success is sanitized and indexed | Measure live-task reuse gain |
| Multimodal | Actual CLIP image embedding, same-image similarity >0.99, scope filters | Real approved SAP captures, visual relevance dataset |
| Templates | Nine blueprints; approved UTF-8 ZIP import, custom XML placeholders, immutable hashes | User-approved SAP export and tenant runtime verification |
| Verifiers/recovery | Independent sandbox state, correlated fresh test MPL, bounded transient retries | Live API/DOM verification; actual allowed repair actions |
| Benchmark | 20 tasks × 4 ablations; executed modes 20/20 | Tenant-held-out tasks and provider comparison |
| Costs/observability | Reservations before optional paid calls; OTel spans/counters | Real provider usage/pricing, collector configuration |
| Fine-tuning | Explicit decision: unnecessary for V1 | Empirical residual weakness + separate budget approval |

Current release validation: **509 tests passed**, including PostgreSQL integration,
in the locked Python 3.12 environment without Torch, Transformers or PEFT.
Chromium exercised the actual local API/UI with an explicitly simulated external
SAP HTTP transport: setup, import, immutable review, async execution, cancellation,
reload recovery, stale-review races, export and mobile layout all passed.
See [browser evidence](validation/SAP-DEV-workspace-ui-validation.json).
These checks do not establish acceptance by a live SAP tenant.

Eight-query retrieval set: Recall@5=0.875, MRR=1.0, nDCG@5=0.9033. Equal simulator
success across tools-only/RAG/trajectory modes does not establish improvement.
Plan-only has no execution success metric. Known 401/429/timeout cases diagnose,
not repair. No production target percentages or paid model results are claimed.

Source reference for CSRF: [SAP Integration Content documentation](https://github.com/SAP-docs/btp-integration-suite/blob/main/docs/ci/Development/integration-content-d1679a8.md).

## Connection and observation update

The dashboard now exposes missing DEV configuration and a read-only connection
probe. CLI deployment and MPL verifiers require observed build/runtime readiness
and fresh correlated message identity/timestamps. Contract tests cover denied
access, malformed OAuth, HTML login responses, wrong artifacts, stale messages,
uncertain request outcomes and bounded polling. A false-positive package-existence
path was corrected. No live tenant request was made in this update. See
[SAP connection setup and limits](SAP_CONNECTION.md).

## Workspace feature update

Added tenant-scoped approved text import, incremental updates, collection filtering,
reopening saved plans and sanitized evidence downloads. Full plans are retained in
new execution records. Fixed stale planning responses, blank request validation and
missing generic-document retrieval routes. Chromium exercised the delayed-response
race, save/reload/reopen/execute flow, real PostgreSQL import/search, deduplication
and mobile layout. See [workspace features](WORKSPACE_FEATURES.md).

## DEV deployment update

Added server-session connection configuration, separate runtime OAuth credentials,
explicit DEV write permission, approved exported-template import, artifact and
request integrity hashes, and a durable background upload/deploy/test/MPL job.
The UI supports run history, cancellation and sanitized evidence downloads.
Connection changes invalidate old plans; replay and existing-iFlow overwrite are
blocked. Successful jobs can contribute scoped summaries when RAG is available.

Runtime tests require an exact response assertion and the flow's own
`SAP_MessageProcessingLogID` response header; deployment readiness alone does not
mean a completed business test. Real tenant acceptance has not been exercised.
No production mode, destructive cleanup or automatic repair has been added.
See the [live workflow](LIVE_WORKFLOW.md) for export constraints and credential
storage, and [planner intents](PLANNER_SUPPORTED_INTENTS.md) for conservative
JMS/SOAP parsing and rejection of unsupported clauses.
