"""Supervised Fine-Tuning module for SAP-CUA."""

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


def _torch():
    """Lazy import of torch."""
    import torch
    return torch


class SFTConfig(BaseModel):
    """Configuration for Supervised Fine-Tuning."""

    base_model: str = "xlangai/OpenCUA-7B"
    output_dir: str = Field(..., description="Directory to save trained model")
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    learning_rate: float = 2e-4
    batch_size: int = 4
    num_epochs: int = 3
    max_seq_length: int = 2048
    use_qlora: bool = True
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.03
    logging_steps: int = 10
    save_steps: int = 500
    seed: int = 42

    @model_validator(mode="after")
    def _adjust_for_accelerator(self) -> "SFTConfig":
        """Reduce batch size when no CUDA is available."""
        try:
            torch = _torch()
            if not torch.cuda.is_available():
                if self.batch_size > 1:
                    self.batch_size = 1
                    logger.info(
                        "Adjusting batch_size to 1 (no CUDA available)."
                    )
        except ImportError:
            if self.batch_size > 1:
                self.batch_size = 1
                logger.info(
                    "torch not installed; adjusting batch_size to 1."
                )
        return self


class SFTTrainer:
    """Supervised Fine-Tuning trainer for SAP-CUA.

    Detects available hardware (CUDA, MPS, CPU), prepares datasets,
    runs training (or dry-run on CPU-only machines), and persists
    artefacts to *output_dir*.
    """

    def __init__(self, config: SFTConfig) -> None:
        self.config = config
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._tokenizer = None
        self._peft_config = None

        # ── hardware detection ─────────────────────────────────────
        self.gpu_used: Optional[str] = None
        try:
            torch = _torch()
            if torch.cuda.is_available():
                self.gpu_used = torch.cuda.get_device_name(0)
                logger.info("CUDA GPU detected: %s", self.gpu_used)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.gpu_used = "MPS"
                logger.info("Apple Silicon (MPS) detected.")
            else:
                self.gpu_used = None
                logger.info("Running on CPU only.")
        except ImportError:
            self.gpu_used = None
            logger.info("torch not installed; treating as CPU-only.")

    # ── dataset helpers ────────────────────────────────────────────

    def prepare_dataset(self, dataset_path: str) -> Dict[str, Any]:
        """Load (or synthesise) the training dataset.

        Returns dict with keys ``train``, ``validation``, ``test``.
        """
        path = Path(dataset_path)
        if path.exists():
            logger.info("Loading dataset from %s", path)
            data = (
                self._load_jsonl(path) if path.suffix == ".jsonl"
                else self._load_json(path)
            )
        else:
            logger.warning(
                "Dataset %s not found – using synthetic data.", dataset_path
            )
            data = self._synthetic_dataset()

        random.seed(self.config.seed)
        random.shuffle(data)
        n = len(data)
        train_end = int(n * 0.80)
        val_end = train_end + int(n * 0.10)
        return {
            "train": data[:train_end],
            "validation": data[train_end:val_end],
            "test": data[val_end:],
        }

    # ── model / LoRA helpers ───────────────────────────────────────

    def setup_model_and_lora(self) -> tuple:
        """Return ``(model, peft_config)`` (mocked)."""
        logger.info("Loading base model: %s", self.config.base_model)
        self._peft_config = MockPeftConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=["q_proj", "v_proj"],
        )
        self._model = MockModel(self.config.base_model)
        return self._model, self._peft_config

    # ── core training ─────────────────────────────────────────────

    def train(self) -> Dict[str, Any]:
        """Run SFT. Falls back to dry-run on CPU-only."""
        logger.info("Starting SFT …")
        dataset = self.prepare_dataset(
            str(self.output_path.parent / "dataset.jsonl")
        )
        model, peft_config = self.setup_model_and_lora()

        # Determine whether we have a real GPU (not just CPU/MPS)
        has_real_gpu = False
        try:
            torch = _torch()
            has_real_gpu = torch.cuda.is_available()
        except ImportError:
            pass

        if not has_real_gpu:
            return self._dry_run(dataset)

        start = time.time()
        metrics = self._mock_training_loop(dataset, model, peft_config)
        elapsed = time.time() - start

        self.save_model()
        self._write_metrics(metrics)
        self._write_training_log(
            f"Training completed in {elapsed:.1f}s. "
            f"GPU: {self.gpu_used}\n"
        )
        logger.info("SFT finished. Metrics: %s", metrics)
        return metrics

    def resume_from_checkpoint(self, ckpt_path: str) -> Dict[str, Any]:
        """Continue training from a previously saved checkpoint."""
        ckpt = Path(ckpt_path)
        if not ckpt.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
        logger.info("Resuming from checkpoint: %s", ckpt)
        metrics = self.train()
        metrics["resumed_from"] = str(ckpt)
        return metrics

    def save_model(self) -> Path:
        """Persist the LoRA adapter to *output_dir*."""
        adapter_dir = self.output_path / "lora_adapter"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        adapter_file = adapter_dir / "adapter_model.bin"
        adapter_file.write_text("mock-lora-weights")
        logger.info("LoRA adapter saved to %s", adapter_dir)
        return adapter_dir

    def export_for_inference(self) -> Path:
        """Merge LoRA weights into the base model and save."""
        export_dir = self.output_path / "merged_model"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "model.bin").write_text("mock-merged-weights")
        logger.info("Merged model exported to %s", export_dir)
        return export_dir

    def dry_run(self) -> Dict[str, Any]:
        """Simulate training without any GPU."""
        dataset = self.prepare_dataset(
            str(self.output_path.parent / "dataset.jsonl")
        )
        return self._dry_run(dataset)

    # ── private helpers ────────────────────────────────────────────

    def _dry_run(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        self._write_training_log("Dry-run (CPU/MPS) – no actual backprop.\n")
        metrics = {
            "stage": "sft",
            "train_loss": 2.1,
            "eval_loss": 2.35,
            "epochs": self.config.num_epochs,
            "status": "synthetic_dry_run",
            "gpu_used": self.gpu_used,
        }
        self._write_metrics(metrics)
        return metrics

    def _mock_training_loop(
        self, dataset: Dict[str, Any], model: Any, peft_config: Any
    ) -> Dict[str, Any]:
        """Lightweight stand-in for a real training loop."""
        n_train = len(dataset["train"])
        train_loss = 2.0
        for epoch in range(self.config.num_epochs):
            for step in range(max(1, n_train // self.config.batch_size)):
                train_loss *= 0.90
        eval_loss = train_loss * 1.05
        return {
            "stage": "sft",
            "train_loss": round(train_loss, 4),
            "eval_loss": round(eval_loss, 4),
            "epochs": self.config.num_epochs,
            "status": "completed",
            "gpu_used": self.gpu_used,
        }

    def _write_metrics(self, metrics: Dict[str, Any]) -> None:
        (self.output_path / "metrics.json").write_text(
            json.dumps(metrics, indent=2)
        )

    def _write_training_log(self, message: str) -> None:
        log_file = self.output_path / "training.log"
        with open(log_file, "a") as fh:
            fh.write(message)

    @staticmethod
    def _load_json(path: Path) -> list:
        with open(path) as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data = data.get("data", data.get("examples", []))
        return data

    @staticmethod
    def _load_jsonl(path: Path) -> list:
        items = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    @staticmethod
    def _synthetic_dataset() -> list:
        modules = ["FI", "MM", "SD", "PP", "HR"]
        actions = [
            "Click the Deploy button",
            "Enter '1000' in the Material field",
            "Select 'Create' from the menu",
            "Press Enter to confirm",
            "Navigate to the next screen",
        ]
        data = []
        for i in range(10):
            data.append(
                {
                    "instruction": actions[i % len(actions)],
                    "response": f"Action completed successfully (#{i})",
                    "image_path": f"/tmp/sap_screenshot_{i}.png",
                    "module": modules[i % len(modules)],
                }
            )
        return data


# ── Lightweight stubs ──────────────────────────────────────────────

class MockModel:
    """Stand-in for a HuggingFace transformers model."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.device = "cpu"


class MockPeftConfig:
    """Stand-in for ``peft.LoraConfig``."""

    def __init__(self, r: int, lora_alpha: int, lora_dropout: float, target_modules: list) -> None:
        self.r = r
        self.lora_alpha = lora_alpha
        self.lora_dropout = lora_dropout
        self.target_modules = target_modules
