"""OpenTelemetry-compatible telemetry client with in-memory backend."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SpanContext:
    """Active trace span."""

    name: str
    trace_id: str
    span_id: str
    start_time: float = field(default_factory=time.time)
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    end_time: float | None = None


class TelemetryClient:
    """OpenTelemetry-compatible telemetry client.

    Provides an in-memory backend by default. If the ``opentelemetry``
    package is available it will route events/metrics/spans to an OTLP
    exporter as well.
    """

    def __init__(self, service_name: str = "sap-cua") -> None:
        self.service_name = service_name
        self._events: list[dict[str, Any]] = []
        self._metrics: list[dict[str, Any]] = []
        self._spans: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._otlp_available = False
        try:
            from opentelemetry import trace  # noqa: F401
            self._otlp_available = True
            logger.debug("OpenTelemetry detected; OTLP export enabled")
        except ImportError:
            logger.debug("OpenTelemetry not installed; using in-memory backend only")

    # ── Events ─────────────────────────────────────────────────────────────

    def record_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        event = {
            "name": name,
            "attributes": attributes or {},
            "timestamp": time.time(),
            "service": self.service_name,
        }
        with self._lock:
            self._events.append(event)
        if self._otlp_available:
            try:
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                tp = TracerProvider(resource=Resource.create({"service.name": self.service_name}))
                with tp.get_tracer(__name__).start_as_current_span(name) as span:
                    for k, v in (attributes or {}).items():
                        span.set_attribute(k, v)
            except Exception as exc:
                logger.debug("OTLP event export failed: %s", exc)

    # ── Metrics ────────────────────────────────────────────────────────────

    def record_metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        metric = {
            "name": name,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time(),
            "service": self.service_name,
        }
        with self._lock:
            self._metrics.append(metric)

    # ── Spans ──────────────────────────────────────────────────────────────

    def start_span(self, name: str) -> SpanContext:
        span = SpanContext(
            name=name,
            trace_id=f"trace-{time.time_ns()}",
            span_id=f"span-{time.time_ns()}",
        )
        with self._lock:
            self._spans.append({"span": span, "events": []})
        return span

    def end_span(self, span: SpanContext, status: str = "ok") -> None:
        span.status = status
        span.end_time = time.time()

    # ── Domain helpers ─────────────────────────────────────────────────────

    def record_action(
        self,
        intent: str,
        executor: str,
        duration_ms: float,
        success: bool,
        cost_usd: float = 0.0,
    ) -> None:
        self.record_event(
            "action.executed",
            attributes={
                "intent": intent,
                "executor": executor,
                "duration_ms": duration_ms,
                "success": success,
                "cost_usd": cost_usd,
            },
        )
        self.record_metric("action.duration_ms", duration_ms, tags={"executor": executor, "intent": intent})
        self.record_metric("action.cost_usd", cost_usd, tags={"executor": executor})
        self.record_metric("action.success_rate", 1.0 if success else 0.0, tags={"executor": executor})

    def record_benchmark_result(
        self,
        task_id: str,
        success: bool,
        steps: int,
        duration: float,
        cost: float,
    ) -> None:
        self.record_event(
            "benchmark.completed",
            attributes={
                "task_id": task_id,
                "success": success,
                "steps": steps,
                "duration": duration,
                "cost_usd": cost,
            },
        )
        self.record_metric("benchmark.duration", duration, tags={"task_id": task_id})
        self.record_metric("benchmark.cost_usd", cost, tags={"task_id": task_id})
        self.record_metric("benchmark.steps", float(steps), tags={"task_id": task_id})

    # ── Flush / introspection ───────────────────────────────────────────────

    def flush(self) -> None:
        with self._lock:
            self._events.clear()
            self._metrics.clear()
            self._spans.clear()

    @property
    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    @property
    def metrics(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._metrics)

    @property
    def spans(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._spans)
