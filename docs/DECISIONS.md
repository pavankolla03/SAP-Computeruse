# SAP-CUA Decision Records

## ADR-001: Primary Base Model — OpenCUA-7B

**Date**: 2025-10-06
**Status**: Accepted

**Context**: We need a 7B multimodal model specialized for computer use.

**Decision**: Use OpenCUA-7B as the primary base model.
**Alternatives considered**: UI-TARS-1.5-7B, OS-Atlas-Pro-7B, 

**Rationale**:
- Already specialized for computer use tasks
- MIT license (commercially permissive)
- Companion tools (AgentNet, AgentNetTool, AgentNetBench)
- vLLM support for production inference
- proven backbone

**Consequences**:
- Training pipeline built around OpenCUA architecture
- All SAP fine-tuning targets OpenCUA checkpoints
- UI-TARS used as competing baseline for benchmarking

## ADR-002: Mock-First Development

**Date**: 2025-10-06
**Status**: Accepted

**Context**: SAP sandbox access may not be immediately available.

**Decision**: Build full mock SAP environment for all development. Real SAP access is a toggle.

**Rationale**:
- Unblocks 90%+ of development
- Enables parallel work across teams
- Reproducible testing
- Zero cost

## ADR-003: Action Priority Philosophy

**Date**: 2025-10-06
**Status**: Accepted

**Decision**: Action priority is API → MCP → Playwright → GUI → Terminal/Code.

**Rationale**:
- API is most reliable and auditable
- GUI is least reliable but necessary fallback
- Model learns to choose executors based on context

## ADR-004: Dataset Sanitization First

**Date**: 2025-10-06
**Status**: Accepted

**Decision**: All datasets pass through automatic secret redaction before training.

**Rationale**:
- Prevent credential leakage in model weights
- Compliance requirement
- Cannot trust human review alone

## ADR-005: Curricular Training Order

**Date**: 2025-10-06
**Status**: Accepted

**Decision**: Train in order: grounding → trajectory → recovery → RL.

**Rationale**:
- Each stage builds on previous
- Grounding is prerequisite for navigation
- Recovery requires navigation + action capability
- RL requires all prior stages working
- Empirical support from GUI-R1 and verl-agent
