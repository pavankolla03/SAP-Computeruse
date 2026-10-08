"""OpenTelemetry SDK instrumentation without exporting task content or secrets.

Configure collectors in the hosting application; the default readers remain local.
"""

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider

trace_provider = TracerProvider()
tracer = trace_provider.get_tracer("sap_cua.engineering")
metric_reader = InMemoryMetricReader()
meter_provider = MeterProvider(metric_readers=[metric_reader])
actions = meter_provider.get_meter("sap_cua.engineering").create_counter("sap_cua.actions")


def metrics_snapshot():
    data = metric_reader.get_metrics_data()
    return data.to_json() if data else "{}"


retrievals = meter_provider.get_meter("sap_cua.rag").create_counter("sap_cua.retrievals")
