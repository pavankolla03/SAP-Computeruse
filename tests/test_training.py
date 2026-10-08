"""Legacy dataset builder tests (SFT correctness is tested separately)."""
import json
import os
import tempfile
from pathlib import Path
import pytest

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
