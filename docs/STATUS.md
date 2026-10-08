# RAG V1 status — 9 October 2026

Working local application; real SAP execution remains unvalidated.

| Area | Evidence | Remaining gate |
|---|---|---|
| Branch preservation | Finetune retains 325c654; development on RAG | None |
| Core/planner/dashboard | Browser requirement → sources → plan → verified run | General free-form planning and complex contracts |
| PostgreSQL/pgvector | Actual native PostgreSQL 17.11, pgvector 0.8.7; version/isolation checks pass | Production least-privilege role + RLS/IAM |
| Text RAG | Actual BGE + MiniLM; 38 original seed objects | Broader approved corpus, held-out evaluation |
| SAP API | OAuth/CSRF, package/artifact/deploy/MPL paths; mock HTTP contracts | DEV credentials and tenant capabilities |
| Playwright | Chromium dynamic pointer insertion and dashboard pass | Real SAP DOM selectors and dialogs |
| CUA | OpenCUA optional adapter + bounded fallback | Practical inference hardware/provider; held-out grounding |
| Trajectory memory | Verified sandbox success is sanitized and indexed | Measure live-task reuse gain |
| Multimodal | Actual CLIP image embedding, same-image similarity >0.99, scope filters | Real approved SAP captures, visual relevance dataset |
| Templates | Nine blueprints; approved ZIP/XML parameterization checks pass | Approved exported SAP iFlow ZIPs and upload/runtime verification |
| Verifiers/recovery | Independent sandbox state, correlated fresh test MPL, bounded transient retries | Live API/DOM verification; actual allowed repair actions |
| Benchmark | 20 tasks × 4 ablations; executed modes 20/20 | Tenant-held-out tasks and provider comparison |
| Costs/observability | Reservations before optional paid calls; OTel spans/counters | Real provider usage/pricing, collector configuration |
| Fine-tuning | Explicit decision: unnecessary for V1 | Empirical residual weakness + separate budget approval |

356 unit/contract/integration tests pass in a clean locked Python 3.12 environment without
Torch, Transformers, or PEFT; the PostgreSQL test is enabled through its test DSN.
Real PostgreSQL and browser integrations are validated outside that unit count.

Eight-query retrieval set: Recall@5=0.875, MRR=1.0, nDCG@5=0.9033. Equal simulator
success across tools-only/RAG/trajectory modes does not establish improvement.
Plan-only has no execution success metric. Known 401/429/timeout cases diagnose,
not repair. No production target percentages or paid model results are claimed.

Source reference for CSRF: [SAP Integration Content documentation](https://github.com/SAP-docs/btp-integration-suite/blob/main/docs/ci/Development/integration-content-d1679a8.md).
