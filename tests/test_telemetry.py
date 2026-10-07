"""Tests for telemetry module."""

from __future__ import annotations

import threading
import time

import pytest

from sap_cua.observability.telemetry import SpanContext, TelemetryClient


@pytest.fixture
def client():
    return TelemetryClient(service_name="test-service")


class TestTelemetryClient:
    def test_record_event(self, client):
        client.record_event("test.event", {"key": "value"})
        events = client.events
        assert len(events) == 1
        assert events[0]["name"] == "test.event"
        assert events[0]["attributes"] == {"key": "value"}

    def test_record_metric(self, client):
        client.record_metric("test.metric", 42.0, tags={"env": "test"})
        metrics = client.metrics
        assert len(metrics) == 1
        assert metrics[0]["value"] == 42.0

    def test_start_and_end_span(self, client):
        span = client.start_span("my_span")
        assert span.name == "my_span"
        assert span.status == "ok"
        client.end_span(span, status="ok")
        assert span.end_time is not None

    def test_record_action(self, client):
        client.record_action("click", "gui", 150.0, True, cost_usd=0.001)
        assert len(client.events) >= 1
        assert len(client.metrics) >= 1

    def test_record_benchmark_result(self, client):
        client.record_benchmark_result("task-1", True, 5, 12.5, 0.05)
        events = client.events
        assert any(e["name"] == "benchmark.completed" for e in events)

    def test_flush(self, client):
        client.record_event("x", {})
        client.record_metric("y", 1.0)
        client.flush()
        assert len(client.events) == 0
        assert len(client.metrics) == 0

    def test_thread_safety(self, client):
        def worker():
            for _ in range(100):
                client.record_event("t", {"i": "1"})
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(client.events) == 400
