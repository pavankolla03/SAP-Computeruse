# Implementation sequence

1. Preserve/audit source; repair false-success paths and trajectory sanitization — done.
2. Installable local workbench, scripted sandbox, persistent runs — implemented.
3. Actual OpenCUA preprocessing/inference and SFT/QLoRA code — implemented;
   full checkpoint loads locally; usable full inference and CUDA training remain unvalidated.
4. Connect scoped SAP tenant and API verifiers; validate artifact upload/deployment,
   functional responses, fresh MPL correlation and resource cleanup.
5. Extend the origin-scoped image-conditioned browser loop, executor bindings and recorder UX,
   recovery cases and resettable SAPWorld tasks. Build a reviewed dataset.
6. Train grounding/trajectory/recovery adapters, run held-out SAPBench with family
   split controls, compare model-only and hybrid baselines at equal budgets.
7. Promote only measured checkpoints; complete registry provenance, cost reservations,
   prompt-injection red-team suite and multi-user security before deployment.
8. Add actual RL/self-play only after reward/verifier reliability is measured.

No phase is complete solely because mock unit tests pass.
