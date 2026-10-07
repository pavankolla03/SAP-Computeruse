# SAP-CUA

> Audited 7 October 2026: this is a prototype. The first integrity repair passes 315 local tests. Real OpenCUA inference, training, live SAP execution and production readiness remain incomplete. See [the audit](docs/AUDIT_2026-10-07.md).
## SAP-Native 7B Computer-Use Agent

SAP-CUA is a research platform and production-oriented multimodal computer-use agent
specialized for SAP Integration Suite. The goal is to autonomously understand natural-language
SAP integration requirements, plan implementations, and execute them across APIs, browser
automation, and visual GUI interaction.

### Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests
make test

# Run the agent
sap-cua run "Create a package called SalesAutomation"

# Run benchmark
sap-cua benchmark --suite sapbench-v1 --model mock

# Start the API server
make dev
```

### Project Structure

```
sap-cua/
├── src/sap_cua/
│   ├── agent/           # Agent loop runtime
│   ├── api/             # FastAPI server
│   ├── evaluation/      # SAPBench benchmark
│   ├── model/           # Model adapters (OpenCUA, UI-TARS, Mock)
│   ├── recorder/        # Trajectory recorder
│   ├── runtime/         # Executors (API, MCP, Playwright, GUI, terminal, code)
│   ├── sap/             # SAP Integration Suite mocks and domain modules
│   ├── security/        # Secret redaction, RBAC, audit
│   ├── services/        # Router, inference, verifier, orchestrator
│   ├── training/        # SFT, QLoRA, RL training pipelines
│   └── types/           # Pydantic models, SAP action language
├── tests/               # 315 local tests
├── infra/docker/        # Docker configuration
└── docs/                # Architecture, strategy, decisions
```

### Benchmark

SAPBench contains **101 task templates** across 5 difficulty levels:

| Level | Description | Tasks |
|-------|-------------|-------|
| 1 | Navigation (open CI, MPL, Security, etc.) | 15 |
| 2 | Basic configuration (create package, iFlow, adapters) | 26 |
| 3 | Integration development (HTTPS→OData, splitter/gather, etc.) | 19 |
| 4 | Debugging (401, timeout, mapping error, missing credential) | 21 |
| 5 | Long-horizon architecture (end-to-end integration build) | 20 |

### Model Strategy

- **Primary base**: OpenCUA-7B (MIT-licensed,  family)
- **Competing baseline**: UI-TARS-1.5-7B (Apache 2.0)
- **Training approach**: LoRA → trajectory SFT → recovery → GRPO RL

### Executor Priority

The agent selects the best execution method automatically:

1. SAP REST API (preferred)
2. MCP/tool
3. Playwright/DOM automation
4. Visual GUI action
5. Terminal/code

### Test Results

The audited baseline had 265 passing tests and 17 errors. The first repair passes
315 tests in an isolated Python 3.12 environment with `src` on `PYTHONPATH`.
These validate local software behavior; they do not demonstrate trained-model or live SAP capability.

The quick-start, installation, CLI and Make targets above still need the reproducibility
repairs listed in the roadmap. The tested direct invocation is:

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

### Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Status](docs/STATUS.md)
- [Decisions](docs/DECISIONS.md)
- [Blockers](docs/BLOCKERS.md)
- [Costs](docs/COSTS.md)
- [Roadmap](docs/ROADMAP.md)

### License

MIT (matches OpenCUA base). See [docs/MODEL_LICENSE_REVIEW.md](docs/MODEL_LICENSE_REVIEW.md).

### Status

Prototype audited; execution/data-integrity repair implemented.
See [docs/STATUS.md](docs/STATUS.md) and [docs/ROADMAP.md](docs/ROADMAP.md).
