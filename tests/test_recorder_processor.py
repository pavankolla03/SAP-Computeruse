"""Tests for sap_cua.recorder.processor."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sap_cua.recorder.processor import QualityScorer, TrajectoryProcessor


@pytest.fixture
def processor(tmp_path):
    return TrajectoryProcessor(storage_dir=str(tmp_path / "trajectories"))


def _make_session(success=True, events=None):
    events = events or [
        {"event_type": "click", "data": {"target": "btn_ok"}, "screenshot": "a.png", "cursor_x": 0.5, "cursor_y": 0.5},
        {"event_type": "type", "data": {"text": "hello"}, "screenshot": "b.png", "cursor_x": 0.5, "cursor_y": 0.5},
        {"event_type": "click", "data": {"target": "btn_submit"}, "screenshot": "c.png", "cursor_x": 0.9, "cursor_y": 0.8},
    ]
    return {
        "task_id": "task-001",
        "mode": "human_demonstration",
        "metadata": {"success": success},
        "events": events,
    }


class TestTrajectoryProcessor:
    def test_load_trajectory(self, tmp_path):
        p = tmp_path / "traj.json"
        p.write_text(json.dumps({"hello": "world"}))
        tp = TrajectoryProcessor(storage_dir=str(tmp_path))
        result = tp.load_trajectory(str(p))
        assert result["hello"] == "world"

    def test_process_session(self, processor):
        session = _make_session()
        result = processor.process_session(session)
        assert result["task_id"] == "task-001"
        assert "steps" in result
        assert len(result["steps"]) == 3
        assert result["success"] is True
        assert "final_verification" in result

    def test_process_session_failure(self, processor):
        session = _make_session(success=False)
        result = processor.process_session(session)
        assert result["success"] is False

    def test_deduplicate_steps(self, processor):
        steps = [
            {"screenshot": "a.png"},
            {"screenshot": "b.png"},
            {"screenshot": "b.png"},
            {"screenshot": "c.png"},
        ]
        result = processor.deduplicate_steps(steps)
        screenshots = [s.get("screenshot") for s in result]
        assert screenshots == ["a.png", "b.png", "c.png"]

    def test_save_trajectory(self, processor, tmp_path):
        trajectory = {"task_id": "t1", "steps": []}
        path = processor.save(trajectory, "test_traj")
        assert Path(path).exists()
        loaded = json.loads(Path(path).read_text())
        assert loaded["task_id"] == "t1"

    def test_compute_quality_score(self, processor):
        trajectory = {
            "steps": [
                {"verification": {"success": True}},
                {"verification": {"success": True}},
            ],
            "success": True,
            "actions_count": 2,
            "duration_ms": 5000,
        }
        score = processor.compute_quality_score(trajectory)
        assert 0.0 <= score <= 1.0

    def test_extract_semantic_actions(self, processor):
        events = [
            {"event_type": "click", "data": {"target": "btn"}},
            {"event_type": "type", "data": {"text": "x"}},
        ]
        actions = processor.extract_semantic_actions(events)
        assert len(actions) == 2


class TestQualityScorer:
    def test_score_action_correctness(self):
        scorer = QualityScorer()
        trajectory = {"steps": [{"verification": {"success": True}}, {"verification": {"success": False}}]}
        score = scorer.score_action_correctness(trajectory)
        assert 0.0 <= score <= 1.0

    def test_score_completeness(self):
        scorer = QualityScorer()
        traj = {"success": True, "steps": [{"event_type": "click"}]}
        assert scorer.score_completeness(traj) == 1.0
        traj2 = {"success": False, "steps": []}
        assert scorer.score_completeness(traj2) == 0.0

    def test_score_efficiency(self):
        scorer = QualityScorer()
        short = scorer.score_efficiency({"steps": [{}] * 5})
        long = scorer.score_efficiency({"steps": [{}] * 50})
        assert short >= long

    def test_score_no_secrets_clean(self):
        scorer = QualityScorer()
        traj = {"steps": [{"data": {"action": "click", "target": "btn"}}]}
        assert scorer.score_no_secrets(traj) == 1.0

    def test_score_no_secrets_leaked(self):
        scorer = QualityScorer()
        traj = {"steps": [{"data": {"password": "secret123"}}]}
        assert scorer.score_no_secrets(traj) < 1.0

    def test_overall_score(self):
        scorer = QualityScorer()
        traj = {
            "success": True,
            "steps": [{"verification": {"success": True}, "data": {"action": "click"}}],
        }
        score = scorer.overall_score(traj)
        assert 0.0 <= score <= 1.0
