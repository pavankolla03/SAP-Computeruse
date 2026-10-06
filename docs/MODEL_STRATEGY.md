# SAP-CUA Model Strategy

## Primary Base Model: OpenCUA-7B

### Rationale

- **Specialized for computer use** — built specifically for GUI grounding and action prediction
- ** family** — proven multimodal backbone
- **MIT License** — commercially permissive
- **Companion tools** — AgentNet dataset, AgentNetTool recorder, AgentNetBench evaluator
- **vLLM support** — production inference
- **Open source** — weights publicly available

### Why Not Larger Models

The goal is to prove **specialization** can outperform generalization. A 7B SAP-specialized model must beat larger frontier models on SAP-specific benchmarks.

## Secondary Baselines

| Model | Size | License | Use |
|-------|------|---------|-----|
| OpenCUA-7B | 7B | MIT | Primary base + baseline |
| UI-TARS-1.5-7B | 7B | Apache 2.0 | Competing open baseline |
| OS-Atlas-Pro-7B | 7B | Apache 2.0 | Grounding baseline |
|  | 7B | Apache 2.0 | General VLM baseline |

## Optional Competitor Adapters (Not Required)

- Navigator n2
- Claude computer use
- OpenAI computer use
- Gemini computer use

These adapters are optional and require API keys. Missing keys do not block development.

## Training Recipe

### Phase 1: Grounding Pretraining (LoRA)
- Dataset: `sap-grounding-v1` (10K+ examples)
- Target: locate SAP UI controls in screenshots
- Output: `sap-cua-7b-v0-grounding`

### Phase 2: Trajectory SFT (LoRA)
- Dataset: `sap-trajectories-v1`
- Multi-step action prediction
- Output: `sap-cua-7b-v0-sft`

### Phase 3: Recovery Training
- Dataset: `sap-recovery-v1`
- Failure detection and remediation
- Output: `sap-cua-7b-v0-recovery`

### Phase 4: RL (GRPO-style)
- Suite: `sapbench-train`
- Rule-based rewards
- Output: `sap-cua-7b-v0-rl`

### Phase 5: Two-stage state-transition + trajectories
- Borrowed from xyliugo/gui-state-transition-pretraining research
- Output: `sap-cua-7b-v0-transition`

## Release Naming

| Version | Description |
|---------|-------------|
| sap-cua-7b-v0.1 | Initial SAP grounding LoRA |
| sap-cua-7b-v0.2-grounding | After grounding training |
| sap-cua-7b-v0.3-trajectory | After trajectory SFT |
| sap-cua-7b-v0.4-recovery | After recovery training |
| sap-cua-7b-v1.0 | Beat baseline open models on SAPBench |