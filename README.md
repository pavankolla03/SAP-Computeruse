# SAP-CUA
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
├── tests/               # 80 unit tests
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

```bash
$ make test
============================= 80 passed in 0.18s ==============================
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

**Phase 3-4**: SAP connector mock + executor router complete.
80/80 tests passing. 101 benchmark templates generated.
See [docs/STATUS.md](docs/STATUS.md) for current state.
