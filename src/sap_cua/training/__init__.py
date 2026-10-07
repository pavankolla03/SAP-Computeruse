"""SAP-CUA training package.

Sub-modules
───────────
* ``sft`` – Supervised Fine-Tuning (SFT) trainer
* ``qlora`` – QLoRA 4-bit quantised fine-tuning
* ``grounding`` – SAP grounding dataset builder
* ``recovery`` – Failure-recovery dataset builder
* ``transition`` – State-transition pretraining dataset builder
"""

from sap_cua.training import grounding, qlora, recovery, sft, transition

__all__ = ["sft", "qlora", "grounding", "recovery", "transition"]
