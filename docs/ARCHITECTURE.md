# SAP-CUA Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE LAYER                            │
│  ┌──────────────┐ ┌────────────────┐ ┌──────────────┐                      │
│  │  Dashboard   │ │  Recorder UI   │ │Agent Console │                      │
│  └──────┬───────┘ └───────┬────────┘ └──────┬───────┘                      │
│         │                 │                  │                               │
│         └─────────────────┴──────────────────┘                               │
│                           REST / WebSocket API                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                            SERVICE LAYER                                     │
│  ┌─────────────┐ ┌───────────────┐ ┌────────────┐ ┌──────────────────┐     │
│  │ Orchestrator│ │ Inference Svc │ │  Verifier  │ │Trajectory Service│     │
│  └──────┬──────┘ └──────┬────────┘ └─────┬──────┘ └────────┬─────────┘     │
│         │                │                  │                  │              │
│  ┌──────┴────────────────┴──────────────────┴──────────────────┴─────────┐  │
│  │                          Executor Router                                │  │
│  │  SAP_API → MCP → PLAYWRIGHT → GUI → TERMINAL → CODE                   │  │
│  └──────┬────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                           MODEL LAYER                                       │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐                 │
│  │  OpenCUA-7B     │  │ UI-TARS-1.5-7B │  │  MockModel   │                 │
│  │  (primary)      │  │ (baseline)     │  │  (dev/test)  │                 │
│  └────────┬────────┘  └───────────────┘  └──────────────┘                 │
│           │                        │                                         │
│    LoRA/QLoRA adapters    Competitor adapters                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                           SAP DOMAIN LAYER                                   │
│  ┌────────────┐ ┌─────────────────┐ ┌──────────┐ ┌───────────────────┐     │
│  │ SAP Actions│ │Cloud Integration│ │   APIM   │ │    Monitoring     │     │
│  │ (DSL)      │ │  (mocks/real)   │ │  (mock)  │ │   (mocks/real)    │     │
│  └────────────┘ └─────────────────┘ └──────────┘ └───────────────────┘     │
├─────────────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE LAYER                                │
│  ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌──────────────────┐    │
│  │ PostgreSQL│ │  Redis  │ │   MinIO  │ │MLflow  │ │   Docker Compose │    │
│  └──────────┘ └─────────┘ └──────────┘ └────────┘ └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Action Priority (Decision Philosophy)

1. **SAP API** — Preferred when available and supported
2. **MCP/tool** — Deterministic, safe, auditable
3. **Playwright/DOM** — Structured browser automation
4. **GUI (visual)** — Last resort for unsupported operations
5. **Terminal/Code** — For generated code execution

## Key Interfaces

| Interface | Purpose |
|-----------|---------|
| `ComputerUseModel` | Model abstraction (observe/plan/act/reset) |
| `SAPMockEnvironment` | Development/test SAP environment |
| `ExecutorRouter` | Selects best executor per action |
| `Verifier` | Programmatic success verification |
| `BenchmarkRunner` | Runs SAPBench evaluation |
