"""QLoRA fine-tuning with quantization for SAP-CUA."""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from sap_cua.training.sft import SFTConfig, SFTTrainer

logger = logging.getLogger(__name__)


def _torch():
    """Lazy import of torch."""
    import torch
    return torch


class QLoRAConfig(SFTConfig):
    """Configuration for QLoRA fine-tuning.

    Extends :class:`SFTConfig` with quantization-specific options.
    """

    quantization_bits: int = Field(default=4, ge=4, le=8)
    use_double_quant: bool = True
    quant_type: str = Field(default="nf4", pattern="^(nf4|fp4)$")
    compute_dtype: str = Field(default="bfloat16", pattern="^(bfloat16|float16)$")

    @field_validator("quantization_bits")
    @classmethod
    def _valid_bits(cls, v: int) -> int:
        if v not in (4, 8):
            raise ValueError("quantization_bits must be 4 or 8")
        return v


class QLoRATrainer(SFTTrainer):
    """QLoRA trainer wrapping :class:`SFTTrainer`.

    Adds 4-bit (or 8-bit) quantisation via BitsAndBytesConfig and
    memory estimation utilities.
    """

    def __init__(self, config: QLoRAConfig) -> None:
        super().__init__(config)  # type: ignore[arg-type]
        self.config: QLoRAConfig = config
        self.bnb_config: Optional[Any] = None

    # ── quantization setup ─────────────────────────────────────────

    def setup_quantization(self) -> Any:
        """Build and return a *BitsAndBytesConfig* (mocked)."""
        logger.info(
            "Setting up %s-bit quantization (%s, double_quant=%s)",
            self.config.quantization_bits,
            self.config.quant_type,
            self.config.use_double_quant,
        )
        self.bnb_config = MockBitsAndBytesConfig(
            load_in_4bit=(self.config.quantization_bits == 4),
            load_in_8bit=(self.config.quantization_bits == 8),
            bnb_4bit_quant_type=self.config.quant_type,
            bnb_4bit_use_double_quant=self.config.use_double_quant,
            bnb_4bit_compute_dtype=self.config.compute_dtype,
        )
        return self.bnb_config

    # ── override train ─────────────────────────────────────────────

    def train(self) -> Dict[str, Any]:
        """QLoRA-specific training with quantised base model."""
        logger.info("Starting QLoRA training …")
        dataset = self.prepare_dataset(
            str(self.output_path.parent / "dataset.jsonl")
        )

        est_gb = self.memory_estimate()
        has_real_gpu = False
        try:
            torch = _torch()
            has_real_gpu = torch.cuda.is_available()
            if has_real_gpu:
                available_gb = self._estimate_gpu_memory()
                if not self.check_memory_fit(available_gb):
                    logger.warning(
                        "Estimated VRAM (%.1f GB) may not fit on %s. "
                        "Consider reducing lora_r or batch_size.",
                        est_gb,
                        self.gpu_used,
                    )
        except ImportError:
            pass

        self.setup_quantization()
        model, peft_config = self.setup_model_and_lora()

        if not has_real_gpu:
            metrics = self._dry_run(dataset)
            metrics["quantization_bits"] = self.config.quantization_bits
            metrics["estimated_vram_gb"] = est_gb
            return metrics

        start = time.time()
        metrics = self._mock_training_loop(dataset, model, peft_config)
        elapsed = time.time() - start
        metrics["quantization_bits"] = self.config.quantization_bits
        metrics["estimated_vram_gb"] = est_gb

        self.save_model()
        self._write_metrics(metrics)
        self._write_training_log(
            f"QLoRA training completed in {elapsed:.1f}s.\n"
        )
        logger.info("QLoRA finished. Metrics: %s", metrics)
        return metrics

    # ── memory utilities ───────────────────────────────────────────

    def memory_estimate(self) -> float:
        """Return estimated VRAM requirement in GB."""
        dtype_bytes = {"bfloat16": 2, "float16": 2}.get(
            self.config.compute_dtype, 2
        )
        base_params = 7e9
        base_vram = (base_params * dtype_bytes) / (1e9 * 8 * self.config.quantization_bits / 4)
        lora_vram = (
            self.config.lora_r * 2 * 12 * dtype_bytes
        ) / 1e9
        activation_vram = (
            self.config.batch_size
            * self.config.max_seq_length
            * 12
            * dtype_bytes
            * 4
        ) / 1e9
        return round(base_vram + lora_vram + activation_vram, 2)

    def check_memory_fit(self, gpu_memory_gb: float) -> bool:
        """Return True if estimated memory fits within *gpu_memory_gb*."""
        est = self.memory_estimate()
        fits = est <= gpu_memory_gb
        logger.info(
            "Memory check: %.1f GB estimated vs %.1f GB available -> %s",
            est,
            gpu_memory_gb,
            "OK" if fits else "OVERFLOW",
        )
        return fits

    def recommend_config(self, gpu_memory_gb: float) -> Dict[str, Any]:
        """Suggest adjusted hyper-parameters to fit *gpu_memory_gb*."""
        recs: Dict[str, Any] = {}
        if not self.check_memory_fit(gpu_memory_gb):
            recs["reduce_batch_size"] = max(1, self.config.batch_size // 2)
            recs["reduce_lora_r"] = max(1, self.config.lora_r // 2)
            recs["use_4bit"] = True
        return recs

    # ── private helpers ────────────────────────────────────────────

    def _estimate_gpu_memory(self) -> float:
        """Best-effort detection of total GPU VRAM in GB."""
        try:
            torch = _torch()
            props = torch.cuda.get_device_properties(0)
            return round(props.total_mem / (1 << 30), 1)
        except Exception:
            return 24.0


class MockBitsAndBytesConfig:
    """Stand-in for ``transformers.BitsAndBytesConfig``."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def __repr__(self) -> str:  # pragma: no cover
        return f"MockBitsAndBytesConfig({self.kwargs})"
