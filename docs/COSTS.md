# SAP-CUA Costs

## Infrastructure Costs (Estimates)

| Item | Monthly Cost |
|------|-------------|
| PostgreSQL (local/Render) | $0-$15 |
| Redis (local/Upstash) | $0-$10 |
| MinIO (local/S3) | $0-$5 |
| MLflow (self-hosted) | $0 |
| Storage (S3) | $0-$10 |

## GPU Training Costs (Estimates)

| Stage | GPU | Hours | Est. Cost |
|-------|-----|-------|-----------|
| Grounding LoRA | A10 | 4 | $12 |
| Trajectory SFT | A10 | 8 | $24 |
| Recovery training | A10 | 4 | $12 |
| RL (GRPO) | A100 40GB | 24 | $120 |
| State transition | A10 | 8 | $24 |

**Total estimated training cost: $200-$500 for V0-V1**

## Cost Governance

- `MAX_JOB_COST_USD=50` — automatic stop for jobs exceeding budget
- All costs tracked in MLflow
- CI runs only cheap tests (no GPU)
- GPU jobs launched conditionally

## Provider-Independent Strategy

The project supports multiple GPU providers without hardcoding:
- Local CUDA
- RunPod
- Vast.ai
- AWS (Graviton + GPU)
- GCP
- Azure

Provider selection is configured at runtime via environment variables.
