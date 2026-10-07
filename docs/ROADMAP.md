# SAP-CUA implementation roadmap

Preserve the useful existing action definitions, environment, types, and utility modules. Deliver connected, verified workflows phase by phase.

## Completed first repair
- [x] Audit current source and run baseline tests.
- [x] Replace confidence-only/unconditional task success with observed-state verification.
- [x] Share execution loop across API and mock benchmark.
- [x] Preserve structured action arguments, reject unsupported mock execution.
- [x] Repair structured sanitization and trajectory persistence.
- [x] Repair local orchestrator/storage contracts and regression tests.

## Next: reproducibility and one vertical workflow
- [ ] Fix package build backend, installation extras and CLI entry points.
- [ ] Fix Makefile, CI dependency installation and Docker/Compose paths.
- [ ] Explicitly separate simulated inference/training artifacts from real capabilities.
- [ ] Integrate policy, tenant scope, budget and audit at the execution boundary.
- [ ] Implement a verified SAP API connector and register real executor capabilities.
- [ ] Execute create/import → deploy → test payload → correlated MPL → verify → cleanup.
- [ ] Validate in local fixtures, then the real SAP sandbox when credentials are available.

## Real inference and data
- [ ] Verify exact OpenCUA-7B checkpoint, processor, image/history format and action grammar.
- [ ] Implement real multimodal inference and deterministic coordinate adapters.
- [ ] Record aligned screenshot/DOM/action/state trajectories.
- [ ] Redact images and review sensitive-field captures before dataset admission.
- [ ] Version immutable manifests and leakage-safe task-family/tenant/time splits.
- [ ] Make each evaluated benchmark task's setup, verification and reset executable.

## Training and later autonomy
- [ ] Implement real grounding LoRA/QLoRA and trajectory SFT.
- [ ] Prove gradients, usable adapter files and reproducible checkpoint reload.
- [ ] Run budget-approved GPU smoke and held-out baseline comparisons.
- [ ] Add recovery training and controlled rollout collection.
- [ ] Add RL only after rewards and sandbox resets are trustworthy.
- [ ] Add authenticated tenant-aware product UI, isolated execution and operational release gates.

Detailed acceptance gates and current gaps: [audit](AUDIT_2026-10-07.md).
