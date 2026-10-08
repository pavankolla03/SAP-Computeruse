# Existing implementation audit — RAG branch, 9 October 2026

Baseline: `325c654`, preserved on `Finetune`. All 329 tests pass, clean locked install
passes, Chromium workflow passes, and GitHub Python 3.11/3.12 plus Docker checks pass.
The application was running at localhost:8765 before this migration.

| Subsystem | Decision | Evidence / next change |
|---|---|---|
| Local web workbench | KEEP / REFACTOR | Real installable UI, durable run records; add requirements, knowledge search and plans |
| Semantic actions | KEEP / EXTEND | Typed action catalog and validation; add complete plan contracts, verifier/rollback metadata |
| Mock SAP environment | KEEP / EXTEND | Explicit resettable simulator; extend saved/configured/tested state and error injection |
| SAP API client | KEEP / EXTEND | OAuth and tested resources; no implicit mock fallback; add artifact operations/CSRF/reads |
| Executor router | KEEP / EXTEND | Trusted authorization and no unsafe write fallback; connect semantic handlers |
| Playwright/browser loop | KEEP / EXTEND | Origin scope and independent verifier; add dynamic insertion and drag contracts |
| Native GUI/code executors | KEEP INACTIVE | Not enabled in V1; require scoped capability and verification before use |
| Recorder/trajectory store | KEEP / REFACTOR | Sanitized persistent records; add verified-success ingestion into trajectory retrieval |
| Text sanitization | KEEP | Pattern based; never claim arbitrary screenshot secret detection |
| Model abstraction | REFACTOR | ComputerUseProvider + planning interface; no hard OpenCUA dependency |
| OpenCUA | KEEP OPTIONAL | Pretrained download/loading works; full action inference too slow on 16 GB Mac |
| LoRA/QLoRA/RL | REMOVE FROM V1 CRITICAL PATH | Preserved on Finetune and optional source modules; no training in RAG product |
| Legacy CLI/API routes | REFACTOR | Remove misleading commands from primary UX; retain source history |
| RAG ingestion/schema | MISSING | Add versioned, scoped knowledge types and incremental content hashing |
| Hybrid retrieval | MISSING | PostgreSQL full text + pgvector + domain routing + reranking + provenance |
| Multimodal retrieval | MISSING | Optional CPU image embeddings with page/module metadata filters |
| Tenant/customer isolation | MISSING | Mandatory trusted scope on ingestion, retrieval, task and memory APIs |
| iFlow artifact templates | MISSING | Validated template contracts and trusted ZIP parameterization; no invented SAP ZIPs |
| Recovery | REFACTOR | Bounded diagnostics/retries and verified repair; no assumed recovery success |
| SAPBench | KEEP / EXTEND | Existing 101 templates are not 101 live tasks; add executable V1 cases and ablations |
| Model registry | KEEP EXPERIMENTAL | Not a V1 planning dependency |
| Costs/telemetry | REFACTOR | Old hardcoded GPU prices unsuitable; explicit provider prices, reservations, real OTel |

Live SAP access and external provider credentials are absent. These prevent live
integration validation, not implementation/testing of deterministic local contracts.
No new fine-tuning work or GPU provisioning belongs in this branch's V1 execution path.
