# Status — 8 October 2026

The original implementation and integrity repairs are preserved in GitHub commit
f9915c6. The next phase provides an installable local application, verified scripted
sandbox workflows, durable sanitized run records, a real OpenCUA inference path,
and actual LoRA/QLoRA training code.

## Validated locally

- Installation, CLI, web API, isolated sandbox workflow, independent final verification.
- Origin/session enforcement, durable results, execution budget, failure stops.
- OAuth and SAP resource contracts against HTTP test transports (not a tenant).
- Screenshot/action preprocessing and real loss/backprop/LoRA weight updates using
  a reduced randomly initialized OpenCUA architecture. This is a software contract
  test, not training or evaluation of the full 7B checkpoint.
- Chromium application workflow and origin restrictions.
- 48 synthetic SAPWorld screenshots/actions with actual browser state verification,
  split as 32 train / 8 validation / 8 test; this is fixture coverage, not real SAP data.
- Full 7B checkpoint loads with CPU/disk offload in about 37 seconds. A complete
  action prediction did not finish within six minutes and the test was terminated.
  Full-model action inference on this Mac is therefore not validated as usable.

## Still required

- Real tenant integration and read-after-write/functional/MPL validation.
- Reviewed SAP screenshots and trajectories with task-family held-out splits.
- Approved CUDA hardware for 7B training; calibrated live benchmark measurements.
- Model-driven semantic planning, real SAP browser tasks, recovery policies and broader SAPWorld coverage.
- Production model promotion, spend accounting across providers, operational security,
  complete prompt-injection evaluations, and real RL optimization.

The shipped local UI deliberately identifies its execution as scripted and mock.
No model benchmark, fine-tuned checkpoint, or production readiness claim is made.
