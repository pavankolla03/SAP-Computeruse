"""Tests for cost tracker module."""

from __future__ import annotations

import os

import pytest

from sap_cua.observability.cost import CostTracker


@pytest.fixture
def tracker():
    return CostTracker()


class TestCostTracker:
    def test_estimate_job_cost_basic(self, tracker):
        cost = tracker.estimate_job_cost({"gpu_type": "H100", "gpu_hours": 2.0, "storage_gb": 10.0})
        # 2*2.0 + (10/30)*0.023 = 4.0 + 0.0077
        assert cost > 3.5
        assert cost < 5.0

    def test_estimate_job_cost_zero(self, tracker):
        cost = tracker.estimate_job_cost({})
        assert cost == 0.0

    def test_record_and_total_spend(self, tracker):
        tracker.record_usage("A100", gpu_hours=1.0)
        tracker.record_usage("A100", gpu_hours=1.0)
        total = tracker.get_total_spend()
        assert abs(total - 3.0) < 0.01

    def test_get_spend_by_model(self, tracker):
        tracker.record_usage("H100", gpu_hours=1.0)
        tracker.record_usage("A10", gpu_hours=1.0)
        by_model = tracker.get_spend_by_model()
        assert "H100" in by_model
        assert "A10" in by_model
        assert by_model["H100"] > by_model["A10"]

    def test_check_budget_within(self, tracker):
        assert tracker.check_budget(10.0, 5.0) is True

    def test_check_budget_exceeds(self, tracker):
        assert tracker.check_budget(1.0, 5.0) is False

    def test_env_max_job_cost(self, monkeypatch):
        monkeypatch.setenv("MAX_JOB_COST_USD", "3.0")
        t2 = CostTracker()
        assert t2._max_job_cost == 3.0
        assert t2.check_budget(10.0, 5.0) is False
        assert t2.check_budget(10.0, 2.0) is True
