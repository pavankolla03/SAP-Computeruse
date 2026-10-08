# Fine-tuning decision — 9 October 2026

**Do not fine-tune for V1.** No GPU run has been launched on RAG.

The first benchmark contains 20 deterministic simulator tasks. Tools-only,
RAG+tools, and RAG+tools+trajectory modes each pass 20/20. RAG plan-only produces
plans but cannot be assigned execution success. Equal success rates are not RAG
uplift. The 8-query curated retrieval set measures Recall@5 0.875, MRR 1.0 and
nDCG@5 0.9033. This sample is too small and too close to the seed corpus to establish
production retrieval quality.

Remaining weaknesses are missing tenant validation, approved exported iFlows,
production integration contracts, real SAP selectors, complex mapping/code tasks,
and externally evaluated visual grounding. These require better data, deterministic
adapters, templates and live evaluation first. They do not justify training.

The downloaded pretrained OpenCUA checkpoint can load on the local 16 GB Mac;
full inference was too slow to validate reliably. The model is optional and not
required for any demonstrated RAG workflow. No cloud-model comparison was run.

Before proposing a focused LoRA experiment: establish held-out tenant tasks,
measure API/DOM/vision failure attribution, compare retrieval/template/recovery
improvements, obtain adequate rights to examples, and approve a GPU budget.
Report live grounding, drag/drop, dialog recovery and per-task cost distributions.
Only train on residual failures that these cheaper methods demonstrably cannot fix.

Finetune preserves the earlier training experiments at commit `325c654`.
