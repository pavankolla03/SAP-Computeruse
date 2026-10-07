"""Tests for SAP-CUA training pipeline."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# ── SFT ────────────────────────────────────────────────────────────


class TestSFTConfig:
    def test_default_values(self):
        from sap_cua.training.sft import SFTConfig

        cfg = SFTConfig(output_dir="/tmp/sft_out")
        assert cfg.base_model == "xlangai/OpenCUA-7B"
        assert cfg.lora_r == 8
        assert cfg.lora_alpha == 16
        assert cfg.lora_dropout == 0.05
        assert cfg.learning_rate == 2e-4
        # batch_size auto-adjusts to 1 when no CUDA is available
        assert cfg.batch_size in (1, 4)
        assert cfg.num_epochs == 3
        assert cfg.max_seq_length == 2048
        assert cfg.use_qlora is True
        assert cfg.gradient_accumulation_steps == 4
        assert cfg.warmup_ratio == 0.03
        assert cfg.logging_steps == 10
        assert cfg.save_steps == 500
        assert cfg.seed == 42

    def test_output_dir_required(self):
        from sap_cua.training.sft import SFTConfig

        with pytest.raises(Exception):  # pydantic ValidationError
            SFTConfig()

    def test_batch_size_adjusted_on_cpu(self, monkeypatch):
        from sap_cua.training.sft import SFTConfig, _torch as _torch_lazy

        fake_torch = type("T", (), {})()
        fake_torch.cuda = type("C", (), {"is_available": staticmethod(lambda: False)})()
        fake_torch.backends = type("B", (), {"mps": type("M", (), {"is_available": staticmethod(lambda: False)})()})()
        monkeypatch.setattr("sap_cua.training.sft._torch", lambda: fake_torch)
        cfg = SFTConfig(output_dir="/tmp/sft_out2", batch_size=4)
        assert cfg.batch_size == 1


class TestSFTTrainer:
    def test_init_creates_output_dir(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            assert Path(cfg.output_dir).exists()

    def test_prepare_dataset_missing_file(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            ds = trainer.prepare_dataset("/nonexistent/path.jsonl")
            assert "train" in ds and "validation" in ds and "test" in ds
            assert len(ds["train"]) > 0

    def test_setup_model_and_lora(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            model, peft = trainer.setup_model_and_lora()
            assert model is not None
            assert peft.r == cfg.lora_r

    def test_train_dry_run_returns_metrics(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            metrics = trainer.train()
            assert metrics["stage"] == "sft"
            assert "train_loss" in metrics
            assert "eval_loss" in metrics
            assert metrics["epochs"] == cfg.num_epochs
            assert metrics["status"] in ("completed", "synthetic_dry_run")

    def test_save_model_creates_adapter(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            trainer.setup_model_and_lora()
            adapter_dir = trainer.save_model()
            assert adapter_dir.exists()
            assert (adapter_dir / "adapter_model.bin").exists()

    def test_export_for_inference(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            export_dir = trainer.export_for_inference()
            assert export_dir.exists()
            assert (export_dir / "model.bin").exists()

    def test_dry_run(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            metrics = trainer.dry_run()
            assert metrics["status"] == "synthetic_dry_run"
            assert metrics["train_loss"] > 0

    def test_train_saves_metrics_and_log(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            trainer.train()
            assert (Path(cfg.output_dir) / "metrics.json").exists()
            assert (Path(cfg.output_dir) / "training.log").exists()
            with open(Path(cfg.output_dir) / "metrics.json") as fh:
                m = json.load(fh)
            assert m["stage"] == "sft"

    def test_resume_from_checkpoint(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            ckpt = Path(td) / "ckpt"
            ckpt.write_text("dummy")
            metrics = trainer.resume_from_checkpoint(str(ckpt))
            assert "resumed_from" in metrics

    def test_resume_missing_checkpoint_raises(self):
        from sap_cua.training.sft import SFTConfig, SFTTrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = SFTConfig(output_dir=os.path.join(td, "out"))
            trainer = SFTTrainer(cfg)
            with pytest.raises(FileNotFoundError):
                trainer.resume_from_checkpoint("/nonexistent/ckpt")


# ── QLoRA ──────────────────────────────────────────────────────────


class TestQLoRAConfig:
    def test_defaults(self):
        from sap_cua.training.qlora import QLoRAConfig

        cfg = QLoRAConfig(output_dir="/tmp/qlora_out")
        assert cfg.quantization_bits == 4
        assert cfg.use_double_quant is True
        assert cfg.quant_type == "nf4"
        assert cfg.compute_dtype == "bfloat16"

    def test_invalid_bits(self):
        from sap_cua.training.qlora import QLoRAConfig

        with pytest.raises(Exception):
            QLoRAConfig(output_dir="/tmp/qlora_out", quantization_bits=3)

    def test_valid_8bit(self):
        from sap_cua.training.qlora import QLoRAConfig

        cfg = QLoRAConfig(output_dir="/tmp/qlora_out", quantization_bits=8, quant_type="fp4")
        assert cfg.quantization_bits == 8
        assert cfg.quant_type == "fp4"

    def test_invalid_quant_type(self):
        from sap_cua.training.qlora import QLoRAConfig

        with pytest.raises(Exception):
            QLoRAConfig(output_dir="/tmp/qlora_out", quant_type="int8")

    def test_invalid_compute_dtype(self):
        from sap_cua.training.qlora import QLoRAConfig

        with pytest.raises(Exception):
            QLoRAConfig(output_dir="/tmp/qlora_out", compute_dtype="float32")

    def test_inherits_sft_fields(self):
        from sap_cua.training.qlora import QLoRAConfig

        cfg = QLoRAConfig(output_dir="/tmp/qlora_out", lora_r=16)
        assert cfg.lora_r == 16
        assert cfg.lora_alpha == 16


class TestQLoRATrainer:
    def test_setup_quantization(self):
        from sap_cua.training.qlora import QLoRAConfig, QLoRATrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = QLoRAConfig(output_dir=os.path.join(td, "out"))
            trainer = QLoRATrainer(cfg)
            bnb = trainer.setup_quantization()
            assert bnb is not None

    def test_train_returns_qlora_metrics(self):
        from sap_cua.training.qlora import QLoRAConfig, QLoRATrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = QLoRAConfig(output_dir=os.path.join(td, "out"))
            trainer = QLoRATrainer(cfg)
            metrics = trainer.train()
            assert "quantization_bits" in metrics
            assert "estimated_vram_gb" in metrics
            assert metrics["stage"] == "sft"

    def test_memory_estimate_positive(self):
        from sap_cua.training.qlora import QLoRAConfig, QLoRATrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = QLoRAConfig(output_dir=os.path.join(td, "out"), quantization_bits=4)
            trainer = QLoRATrainer(cfg)
            est = trainer.memory_estimate()
            assert est > 0

    def test_check_memory_fit(self):
        from sap_cua.training.qlora import QLoRAConfig, QLoRATrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = QLoRAConfig(output_dir=os.path.join(td, "out"))
            trainer = QLoRATrainer(cfg)
            est = trainer.memory_estimate()
            assert trainer.check_memory_fit(est + 10.0) is True
            assert trainer.check_memory_fit(0.1) is False

    def test_recommend_config_on_overflow(self):
        from sap_cua.training.qlora import QLoRAConfig, QLoRATrainer

        with tempfile.TemporaryDirectory() as td:
            cfg = QLoRAConfig(output_dir=os.path.join(td, "out"), batch_size=4, lora_r=8)
            trainer = QLoRATrainer(cfg)
            recs = trainer.recommend_config(1.0)
            assert "reduce_batch_size" in recs or "reduce_lora_r" in recs


# ── Grounding ──────────────────────────────────────────────────────


class TestGroundingExample:
    def test_model_validation(self):
        from sap_cua.training.grounding import GroundingExample

        ex = GroundingExample(
            image_path="/img/1.png",
            instruction="Click Deploy",
            target={"bbox": [10, 20, 100, 50]},
            module="FI",
            confidence=0.95,
        )
        assert ex.confidence == 0.95

    def test_confidence_validation(self):
        from sap_cua.training.grounding import GroundingExample

        with pytest.raises(Exception):
            GroundingExample(
                image_path="/img/1.png",
                instruction="Click Deploy",
                target={"bbox": [0, 0, 10, 10]},
                module="FI",
                confidence=2.0,
            )


class TestGroundingDatasetBuilder:
    def test_add_example(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_example("/img/1.png", "Click X", {"bbox": [0, 0, 10, 10]}, "MM")
        assert len(b._examples) == 1

    def test_add_from_screenshot(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_from_screenshot("/img/1.png", "#deploy-btn", "Click Deploy", "FI")
        assert len(b._examples) == 1
        assert "bbox" in b._examples[0].target

    def test_split(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        for i in range(10):
            b.add_example(f"/img/{i}.png", f"Do {i}", {"bbox": [0, 0, 1, 1]}, "FI")
        splits = b.split()
        assert "train" in splits
        assert "validation" in splits
        assert "test" in splits
        total = sum(len(v) for v in splits.values())
        assert total == 10

    def test_save_and_load_jsonl(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_example("/img/1.png", "Click X", {"bbox": [0, 0, 10, 10]}, "MM")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            p = f.name
        try:
            b.save(p)
            b2 = GroundingDatasetBuilder()
            b2.load(p)
            assert len(b2._examples) == 1
        finally:
            os.unlink(p)

    def test_get_statistics(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_example("/img/1.png", "Click", {"bbox": [0, 0, 1, 1]}, "MM")
        b.add_example("/img/2.png", "Type", {"point": [5, 5]}, "FI")
        stats = b.get_statistics()
        assert stats["total_examples"] == 2
        assert stats["by_module"]["MM"] == 1

    def test_filter_by_confidence(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_example("/img/1.png", "A", {"bbox": [0, 0, 1, 1]}, "FI", confidence=0.9)
        b.add_example("/img/2.png", "B", {"bbox": [0, 0, 1, 1]}, "FI", confidence=0.3)
        b.filter_by_confidence(0.5)
        assert len(b._examples) == 1

    def test_augment(self):
        from sap_cua.training.grounding import GroundingDatasetBuilder

        b = GroundingDatasetBuilder()
        b.add_example("/img/1.png", "Click", {"bbox": [0, 0, 1, 1]}, "FI")
        augmented = b.augment(zoom_level=1.5)
        assert len(augmented) == 1
        assert augmented[0].confidence < 1.0


# ── Recovery ───────────────────────────────────────────────────────


class TestRecoveryExample:
    def test_model_validation(self):
        from sap_cua.training.recovery import RecoveryExample

        ex = RecoveryExample(
            failure_type="401",
            before_state={"status": "ok"},
            diagnosis="Unauthorized",
            remediation="Re-auth",
            after_state={"status": "recovered"},
            actions=[{"a": 1}],
            success=True,
        )
        assert ex.failure_type == "401"


class TestRecoveryDatasetBuilder:
    def test_add_failure(self):
        from sap_cua.training.recovery import RecoveryDatasetBuilder

        b = RecoveryDatasetBuilder()
        b.add_failure(
            "timeout",
            {"status": "failed"},
            "Connection timed out",
            "Retry with backoff",
        )
        assert len(b._examples) == 1

    def test_generate_from_mpl(self):
        from sap_cua.training.recovery import RecoveryDatasetBuilder

        b = RecoveryDatasetBuilder()
        entries = [
            {"error_code": "401", "description": "Auth failed", "timestamp": "2024-01-01"}
        ]
        examples = b.generate_from_mpl(entries)
        assert len(examples) == 1
        assert examples[0].failure_type == "401"

    def test_augment_variations(self):
        from sap_cua.training.recovery import RecoveryDatasetBuilder, RecoveryExample

        b = RecoveryDatasetBuilder()
        base = RecoveryExample(
            failure_type="403",
            before_state={},
            diagnosis="Forbidden",
            remediation="Refresh token",
            after_state={},
            actions=[],
            success=True,
        )
        variations = b.augment_variations(base)
        assert len(variations) == 3

    def test_save_and_load_jsonl(self):
        from sap_cua.training.recovery import RecoveryDatasetBuilder

        b = RecoveryDatasetBuilder()
        b.add_failure("401", {"s": 1}, "No auth", "Re-auth")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            p = f.name
        try:
            b.save(p)
            b2 = RecoveryDatasetBuilder()
            b2.load(p)
            assert len(b2._examples) == 1
        finally:
            os.unlink(p)

    def test_get_statistics(self):
        from sap_cua.training.recovery import RecoveryDatasetBuilder

        b = RecoveryDatasetBuilder()
        b.add_failure("401", {}, "A", "R1")
        b.add_failure("timeout", {}, "B", "R2")
        stats = b.get_statistics()
        assert stats["total_examples"] == 2
        assert stats["success_rate"] == 1.0


# ── Transition ─────────────────────────────────────────────────────


class TestStateTransitionExample:
    def test_model_validation(self):
        from sap_cua.training.transition import StateTransitionExample

        ex = StateTransitionExample(
            before_image="/s1.png",
            after_image="/s2.png",
            action="Click Deploy",
            transition_type="click",
            module="FI",
        )
        assert ex.transition_type == "click"


class TestTransitionDatasetBuilder:
    def test_add_transition(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Click Deploy", "FI")
        assert len(b._examples) == 1
        assert b._examples[0].transition_type == "click"

    def test_generate_inverse(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Click X", "FI")
        inv = b.generate_inverse()
        assert len(inv) == 1
        assert inv[0].transition_type == "inverse"
        assert inv[0].before_image == "/s2.png"

    def test_generate_forward(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Type text", "FI")
        fwd = b.generate_forward()
        assert len(fwd) == 1
        assert fwd[0].transition_type == "forward"

    def test_deduplicate(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Click X", "FI")
        b.add_transition("/s1.png", "/s2.png", "Click X", "FI")
        removed = b.deduplicate()
        assert removed == 1
        assert len(b._examples) == 1

    def test_save_and_load_json(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Click", "MM")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            p = f.name
        try:
            b.save(p)
            b2 = TransitionDatasetBuilder()
            b2.load(p)
            assert len(b2._examples) == 1
        finally:
            os.unlink(p)

    def test_classify_drag(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Drag slider", "FI")
        assert b._examples[0].transition_type == "drag"

    def test_classify_type(self):
        from sap_cua.training.transition import TransitionDatasetBuilder

        b = TransitionDatasetBuilder()
        b.add_transition("/s1.png", "/s2.png", "Enter value", "MM")
        assert b._examples[0].transition_type == "type"
