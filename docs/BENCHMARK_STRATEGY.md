# SAP-CUA Benchmark Strategy

## SAPBench Design

SAPBench follows OSWorld-V2's methodology: versioned, resettable evaluation environments.

### Task Levels

| Level | Description | Target Count | Skills Tested |
|-------|-------------|-------------|---------------|
| 1 | Navigation | 50+ | UI grounding, navigation |
| 2 | Basic configuration | 100+ | Package/iFlow creation, adapter config |
| 3 | Integration development | 100+ | Component assembly, routing, mapping |
| 4 | Debugging | 100+ | Error diagnosis, recovery |
| 5 | Long-horizon architecture | 50+ | End-to-end integration building |

**Total target: 400+ tasks**

### Evaluation Protocol

- Same benchmark, same starting state, same time limit, same max actions
- 5+ attempts per task (multiple seeds)
- Report confidence intervals
- Fixed verifier (programmatic, not self-reported)

### Competitors

| Model | Adapter Status |
|-------|---------------|
| SAP-CUA-7B | Native |
| OpenCUA-7B | Built-in adapter |
| UI-TARS-1.5-7B | Built-in adapter |
| OS-Atlas-Pro-7B | Optional |
| Claude computer use | Optional (API key required) |
| OpenAI computer use | Optional (API key required) |
| Gemini computer use | Optional (API key required) |
| Navigator n2 | Optional (API required) |

### Metrics

| Metric | Description |
|--------|-------------|
| Task success rate | % tasks fully completed |
| Step accuracy | % correct actions per step |
| Grounding accuracy | % correct UI element targeting |
| Recovery rate | % failures successfully recovered |
| Actions per task | Efficiency |
| Time per task | Speed |
| Tokens per task | Cost proxy |
| Human intervention rate | Autonomy measure |
| Unsafe action rate | Safety |
| Unrelated modification rate | Precision |
| API-vs-GUI selection quality | Routing accuracy |

### Success Targets

| Version | Target |
|---------|--------|
| V0.1 | Grounding 95% |
| V0.2 | Navigation 95% |
| V0.3 | Basic config 90% |
| V0.4 | Adapter config 90% |
| V0.5 | Deploy/test/MPL 85% |
| V0.6 | Debugging 75% |
| V1.0 | Beat frontier models by 5pp |
