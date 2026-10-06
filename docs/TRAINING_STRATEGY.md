# SAP-CUA Training Strategy

## Hardware Requirements

| Stage | GPU Memory | Recommended Hardware |
|-------|-----------|---------------------|
| Grounding (LoRA) | ~8GB | RTX 4090 / A10 |
| Trajectory SFT (LoRA) | ~12GB | RTX 4090 / A10 / A100 |
| Recovery training | ~12GB | RTX 4090 / A10 |
| QLoRA | ~8GB | RTX 3060 12GB |
| RL (GRPO) | ~16GB | A100 40GB+ |

## Training Stack

- **Transformers** + **PEFT** — LoRA/QLoRA fine-tuning
- **DeepSpeed ZeRO-2** — distributed training
- **Accelerate** — trainer abstraction
- **TRL** — SFT/DPO/GRPO when applicable
- **vLLM** — fast inference

## Training Order (E0-E10)

```
E0: OpenCUA-7B untouched baseline
    → Record benchmark metrics

E1: SAP grounding LoRA
    → Target: 95% grounding on common controls

E2: SAP trajectory LoRA
    → Target: 80% Level 3 tasks

E3: Mixed training (grounding + trajectory)
    → Prevent catastrophic forgetting

E4: Generic AgentNet replay mixed with SAP
    → Maintain generic GUI ability

E5: Recovery dataset added
    → Target: 75% recovery rate

E6: State transition pretraining (if justified)
    → Two-stage recipe

E7: RL on Level 1/2 tasks
    → GRPO with rule-based rewards

E8: RL on Level 3 tasks
    → Harder environment rollouts

E9: Failure recovery RL
    → Optimize reward for recovery

E10: Long-horizon curriculum
    → Stage G/H tasks
```

## Reproducibility

- Fixed random seeds
- Deterministic training configs
- Dataset versions tracked
- Model checkpoints versioned
- Experiment logging to MLflow
