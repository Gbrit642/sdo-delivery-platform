"""Google Cloud AI Agent OpenTelemetry Tracing & Observability Instrumentation."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Attempt importing opentelemetry with graceful mock fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider()
    memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("sdo.adk.engine", "0.1.0")
except ImportError:
    memory_exporter = None

    # Graceful fallback mock tracer
    class MockSpan:
        def __init__(self, name: str = "", attributes: dict[str, Any] | None = None):
            self.name = name
            self.attributes = attributes or {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def record_exception(self, e):
            pass

        def set_status(self, status, description=""):
            pass

    class MockTracer:
        def __init__(self):
            self.spans = []

        def start_as_current_span(self, name: str, attributes: dict[str, Any] | None = None):
            span = MockSpan(name=name, attributes=attributes)
            self.spans.append(span)
            return span

    tracer = MockTracer()  # type: ignore


def get_in_memory_spans() -> list[Any]:
    """Retrieve captured OpenTelemetry spans for test verification."""
    if memory_exporter is not None:
        return list(memory_exporter.get_finished_spans())
    if hasattr(tracer, "spans"):
        return list(tracer.spans)
    return []


def clear_in_memory_spans() -> None:
    """Clear recorded spans in memory exporter."""
    if memory_exporter is not None:
        memory_exporter.clear()
    if hasattr(tracer, "spans"):
        tracer.spans.clear()


@contextmanager
def trace_agent_step(
    node_name: str, loop_id: str, attributes: dict[str, Any] | None = None
) -> Generator[Any, None, None]:
    """Context manager wrapping state graph node execution with OpenTelemetry spans."""
    attrs = {
        "sdo.loop_id": loop_id,
        "sdo.node_name": node_name,
        "gen_ai.system": "google_vertex_ai",
        "gen_ai.request.model": "gemini-3.7-flash",
    }
    if attributes:
        attrs.update(attributes)

    with tracer.start_as_current_span(f"sdo.node.{node_name.lower()}", attributes=attrs) as span:
        logger.debug("Started OTel trace span for node '%s' (loop: %s)", node_name, loop_id)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(getattr(trace, "StatusCode", None) and trace.StatusCode.ERROR, str(e))
            raise
