# SAP-CUA Roadmap

## Phase 0 — Foundation (Current)
- [x] Project structure
- [x] SAP Semantic Action Language
- [x] Model abstraction (OpenCUA, UI-TARS, Mock)
- [x] SAP Mock Environment
- [x] Executor Router
- [x] Verifier framework
- [x] SAPBench task generator + runner
- [x] Security redaction
- [x] Docker configuration
- [x] 40+ unit tests
- [ ] GitHub repository push
- [ ] pip install + test run

## Phase 1 — Reproducible Dev Environment
- [ ] Full docker-compose stack
- [ ] Bootstrap script (macOS + Linux)
- [ ] MLflow integration
- [ ] CI/CD pipeline

## Phase 2 — Baseline Model Harness
- [ ] Transformers inference for OpenCUA-7B
- [ ] vLLM inference support
- [ ] Competitor adapters (optional)
- [ ] Baseline metrics on SAPBench

## Phase 3 — SAP Sandbox Connector
- [ ] OAuth client-credentials flow
- [ ] IntegrationPackages API client
- [ ] IntegrationDesigntimeArtifacts API client
- [ ] MPL API client
- [ ] Security Material API client
- [ ] Retry, rate limiting, CSRF handling

## Phase 4 — Executor Router
- [ ] Policy-based routing
- [ ] Fallback chains
- [ ] Reason logging

## Phase 5 — Recorder
- [ ] Desktop overlay
- [ ] Screenshot capture
- [ ] Event logging
- [ ] Replay mode

## Phase 6 — Trajectory Processor
- [ ] Deduplication
- [ ] Secret sanitization
- [ ] State/action alignment
- [ ] Quality scoring

## Phase 7 — Annotation
- [ ] DOM-based auto-labeling
- [ ] LLM-assisted annotation
- [ ] Review queue

## Phase 8 — SAPBench
- [ ] 400+ tasks across 5 levels
- [ ] Versioned releases
- [ ] Competitor evaluation harness

## Phase 9 — Verifiers
- [ ] 15+ verifier functions
- [ ] Automatic environment reset
- [ ] Cleanup automation

## Phase 10 — Self-Rollout
- [ ] Async worker pool
- [ ] Task generator
- [ ] Trajectory store
- [ ] Quality scoring

## Phases 11-52
See MASTER BUILD PROMPT for full details.
