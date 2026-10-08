"""QLoRA shares the real SFT implementation; quantization requires CUDA/bitsandbytes."""

from typing import Literal
from sap_cua.training.sft import SFTConfig, SFTTrainer


class QLoRAConfig(SFTConfig):
    use_qlora: Literal[True] = True


class QLoRATrainer(SFTTrainer):
    def __init__(self, config: QLoRAConfig):
        super().__init__(config)
