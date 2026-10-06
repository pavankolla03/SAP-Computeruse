# SAP-CUA Data Strategy

## Data Sources

### Source A: Existing Open Computer-Use Data
- AgentNet for generic GUI grounding preservation
- OSWorld for desktop UI patterns
- **Goal**: Maintain generic GUI ability while specializing

### Source B: Human SAP Demonstrations
- **Initial target**: 50-100 canonical high-quality SAP workflows
- Highest-value training data
- Captured via the Recorder UI

### Source C: Deterministic Generated Trajectories
- Use API results to generate:
  - goal
  - before state
  - after state
  - semantic actions
  - verification results

### Source D: Agent Self-Rollouts
- Once base agent works:
  - generate task
  - agent attempts
  - automatic verifier
  - keep successful trajectory
  - store failed trajectories separately
- This becomes the **primary scaling method**

## Dataset Versioning

| Dataset | Content | Version |
|---------|---------|---------|
| sap-grounding-v1 | 10K+ UI grounding examples | v1 |
| sap-transition-v1 | State transitions | v1 |
| sap-trajectories-v1 | Multi-step workflows | v1 |
| sap-recovery-v1 | Failure/recovery examples | v1 |
| sapbench-v1 | Benchmark (held out) | v1 |

## Security

- NO real production credentials in datasets
- Automatic secret redaction
- Symbolic placeholders: `<REDACTED_PASSWORD>`, etc.
- Only symbolic references in training data

## Curriculum

| Stage | Content | Target |
|-------|---------|--------|
| A | UI grounding | 95% |
| B | Single action | 95% |
| C | 3-5 step workflows | 90% |
| D | 10-30 step workflows | 80% |
| E | Complex integration | 75% |
| F | Failure recovery | 75% |
| G | Architecture tasks | 70% |
| H | Cross-module workflows | 65% |
