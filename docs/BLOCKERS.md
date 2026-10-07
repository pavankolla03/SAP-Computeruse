# External dependencies and blockers

Repository access is available at `/Users/it-stock/Desktop/SAP_Computer_USE`.
Git is already initialized. Preserve the current repository and its uncommitted changes.

Local engineering is not blocked by SAP credentials or GPUs. Implement and verify local contracts, fixtures, packaging, inference adapters, and data processing first.

Before live SAP validation: obtain a sandbox tenant and scoped authentication; user handles any required MFA. Do not use production tenants as test fixtures.
Before real GPU training: validate the real training pipeline, choose compute, define a spending cap, and obtain authorization for actual GPU/cloud spend.
Before distribution or competitor claims: verify upstream model/dataset licensing, exact revisions and matched evaluation conditions.

No trained checkpoint or validated SAP demonstration dataset exists in the inspected repository. These must be produced; they are not just configuration switches.
