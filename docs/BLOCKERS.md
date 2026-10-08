# External requirements

1. **Development SAP tenant:** URL, scoped service-key/OAuth configuration and
   sandbox resource permissions. Store secrets in an ignored environment file or
   secret manager, never chat or source control. First validate read-only access;
   tenant mutation and cleanup require an explicit resource scope.
2. **Training data:** verified, sanitized screenshots/action trajectories. Existing
   placeholder data and generated success labels must not become ground truth.
3. **Training hardware:** a provisioned CUDA GPU with adequate memory, plus an
   approved spend/time limit if paid. The current M1 Pro has 16 GB unified memory.
   No paid compute has been started.

These block live validation and a SAP-fine-tuned checkpoint, not local development.
Full application completion and benchmark superiority remain unproven.
