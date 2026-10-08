"""Actual screenshot-conditioned LoRA SFT. Validation never reports training metrics."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from PIL import Image

from sap_cua.model.opencua import OpenCUARuntime, parse_action, resized_dimensions
from sap_cua.security import sanitize_data


class SFTConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_model: str = ".models/OpenCUA-7B"
    dataset_path: str = "dataset.jsonl"
    output_dir: str
    lora_r: int = Field(8, ge=1, le=128)
    lora_alpha: int = Field(16, ge=1)
    lora_dropout: float = Field(0.05, ge=0, lt=1)
    learning_rate: float = Field(2e-4, gt=0)
    num_epochs: int = Field(3, ge=1)
    max_seq_length: int = Field(4096, ge=128)
    use_qlora: bool = False
    gradient_accumulation_steps: int = Field(4, ge=1)
    warmup_ratio: float = Field(0.03, ge=0, lt=1)
    logging_steps: int = Field(10, ge=1)
    save_steps: int = Field(100, ge=1)
    max_steps: int = Field(100, ge=1, le=100000)
    seed: int = 42


def load_dataset(path: str) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Explicit family-grouped splits, verified labels, bounded local image paths."""
    source = Path(path).resolve(strict=True)
    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    families: dict[str, str] = {}
    images: dict[str, str] = {}
    digest = hashlib.sha256(source.read_bytes())
    for number, line in enumerate(source.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        for key in ("instruction", "response", "image_path", "family", "split"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Row {number}: {key} is required")
        split, family = row["split"], row["family"]
        if split not in splits:
            raise ValueError(f"Row {number}: invalid split")
        if row.get("verified") is not True or row.get("image_sanitized") is not True:
            raise ValueError(f"Row {number}: verified action and reviewed/redacted image required")
        if row.get("source") not in ("human", "validated_teacher", "sandbox"):
            raise ValueError(f"Row {number}: explicit data source required")
        if sanitize_data({"text": row["instruction"], "response": row["response"]}) != {
            "text": row["instruction"],
            "response": row["response"],
        }:
            raise ValueError(f"Row {number}: secret-like text must be redacted before training")
        image_path = (source.parent / row["image_path"]).resolve(strict=True)
        if not image_path.is_relative_to(source.parent):
            raise ValueError(f"Row {number}: image must be inside dataset directory")
        content = image_path.read_bytes()
        image_hash = hashlib.sha256(content).hexdigest()
        if (
            families.setdefault(family, split) != split
            or images.setdefault(image_hash, split) != split
        ):
            raise ValueError(f"Row {number}: family or duplicate screenshot leaks across splits")
        with Image.open(image_path) as image:
            w, h = resized_dimensions(*image.size)
            parse_action(row["response"], w, h)
        row["image_path"] = str(image_path)
        row["image_sha256"] = image_hash
        digest.update(content)
        splits[split].append(row)
    if not splits["train"] or not splits["validation"]:
        raise ValueError("Non-empty train and validation splits are required")
    manifest = {
        "sha256": digest.hexdigest(),
        "counts": {k: len(v) for k, v in splits.items()},
        "family_count": len(families),
        "image_review": "attested_by_dataset_author",
    }
    return splits, manifest


class SFTTrainer:
    def __init__(self, config: SFTConfig):
        self.config = config
        self.output_path = Path(config.output_dir)
        self._model = None
        self.runtime = OpenCUARuntime(config.base_model)

    def prepare_dataset(self, dataset_path: str):
        return load_dataset(dataset_path)[0]

    def dry_run(self):
        _, manifest = load_dataset(self.config.dataset_path)
        return {"status": "validated_only", "trained": False, "dataset": manifest}

    def setup_model_and_lora(self):
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "7B training requires a configured CUDA GPU. No training occurred; no cloud GPU was started."
            )
        from transformers import AutoModel, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        kwargs = {
            "trust_remote_code": True,
            "local_files_only": True,
            "torch_dtype": torch.bfloat16,
            "attn_implementation": "sdpa",
            "device_map": {"": torch.cuda.current_device()},
        }
        if self.config.use_qlora:
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        model = AutoModel.from_pretrained(self.config.base_model, **kwargs)
        # Freeze vision; adapt language attention and MLP only.
        for parameter in model.parameters():
            parameter.requires_grad = False
        if self.config.use_qlora:
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        lora = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=r"language_model\.model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))",
            bias="none",
        )
        self._model = get_peft_model(model, lora)
        self._model.config.use_cache = False
        self._model.enable_input_require_grads()
        self._model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        return self._model, lora

    def train(self, *, resume_from_checkpoint: str | None = None):
        splits, manifest = load_dataset(self.config.dataset_path)
        if (
            self.output_path.exists()
            and any(self.output_path.iterdir())
            and resume_from_checkpoint is None
        ):
            raise ValueError(
                "Output directory is not empty; use a new directory or resume an actual checkpoint"
            )
        import torch
        from transformers import Trainer, TrainingArguments, set_seed

        set_seed(self.config.seed)
        self.runtime.load_processor()
        # Fail on oversized samples; truncating image tokens corrupts the input.
        runtime, config = self.runtime, self.config

        class ScreenshotDataset(torch.utils.data.Dataset):
            def __init__(self, rows):
                self.rows = rows

            def __len__(self):
                return len(self.rows)

            def __getitem__(self, index):
                row = self.rows[index]
                with Image.open(row["image_path"]) as image:
                    sample = runtime.prepare(image, row["instruction"], row["response"])
                if sample["input_ids"].shape[1] > config.max_seq_length:
                    raise ValueError(
                        "Example exceeds max_seq_length; reduce image budget or instruction size"
                    )
                return sample

        model, _ = self.setup_model_and_lora()
        self.output_path.mkdir(parents=True, exist_ok=True)
        (self.output_path / "dataset-manifest.json").write_text(json.dumps(manifest, indent=2))
        (self.output_path / "training-config.json").write_text(config.model_dump_json(indent=2))
        args = TrainingArguments(
            output_dir=str(self.output_path),
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            num_train_epochs=config.num_epochs,
            max_steps=config.max_steps,
            bf16=True,
            warmup_ratio=config.warmup_ratio,
            logging_steps=config.logging_steps,
            save_steps=config.save_steps,
            save_total_limit=2,
            eval_strategy="steps",
            eval_steps=config.save_steps,
            remove_unused_columns=False,
            report_to=[],
            label_names=["labels"],
            seed=config.seed,
        )
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=ScreenshotDataset(splits["train"]),
            eval_dataset=ScreenshotDataset(splits["validation"]),
            data_collator=single_example_collator,
        )
        result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
        metrics = {
            **result.metrics,
            **trainer.evaluate(),
            "status": "trained",
            "dataset_sha256": manifest["sha256"],
        }
        self.save_model()
        (self.output_path / "metrics.json").write_text(json.dumps(metrics, indent=2))
        return metrics

    def resume_from_checkpoint(self, ckpt_path: str):
        checkpoint = Path(ckpt_path)
        if not (checkpoint / "trainer_state.json").is_file():
            raise FileNotFoundError("A real Trainer checkpoint with trainer_state.json is required")
        previous_manifest = self.output_path / "dataset-manifest.json"
        _, manifest = load_dataset(self.config.dataset_path)
        if (
            not previous_manifest.exists()
            or json.loads(previous_manifest.read_text())["sha256"] != manifest["sha256"]
        ):
            raise ValueError("Dataset changed or original manifest is missing")
        return self.train(resume_from_checkpoint=str(checkpoint))

    def save_model(self):
        if self._model is None:
            raise RuntimeError("No model has been trained or loaded")
        destination = self.output_path / "lora_adapter"
        self._model.save_pretrained(destination, safe_serialization=True)
        return destination

    def export_for_inference(self):
        if self._model is None:
            raise RuntimeError("No model has been loaded")
        if self.config.use_qlora:
            raise RuntimeError("Reload the adapter against a non-quantized base before merging")
        destination = self.output_path / "merged_model"
        self._model.merge_and_unload().save_pretrained(destination, safe_serialization=True)
        return destination


def single_example_collator(samples):
    if len(samples) != 1:
        raise ValueError("Variable image grids require batch size 1; use gradient accumulation")
    return samples[0]
