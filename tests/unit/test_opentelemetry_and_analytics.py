"""Unit tests verifying OpenTelemetry Cloud Trace instrumentation and BigQuery Agent Analytics."""

import pytest
from graphs.state import ActorIdentity, LoopState
from graphs.workflow import SDOStateGraph
from observability.otel import (
    clear_in_memory_spans,
    get_in_memory_spans,
    trace_agent_step,
)
from observability.analytics import AnalyticsEvent, BigQueryAgentAnalytics


@pytest.mark.asyncio
async def test_opentelemetry_spans_contain_gemini_37_and_loop_id():
    """Verify that OpenTelemetry spans capture gen_ai.request.model=gemini-3.7-flash and sdo.loop_id."""
    clear_in_memory_spans()

    loop_id = "01KZZOTELTEST000000001"
    node_name = "SPECIFY"

    with trace_agent_step(node_name=node_name, loop_id=loop_id, attributes={"sdo.domain": "finance"}):
        # Execute synthetic step
        pass

    spans = get_in_memory_spans()
    assert len(spans) >= 1

    target_span = spans[-1]
    attrs = target_span.attributes if hasattr(target_span, "attributes") else {}

    assert attrs.get("sdo.loop_id") == loop_id
    assert attrs.get("sdo.node_name") == node_name
    assert attrs.get("gen_ai.request.model") == "gemini-3.7-flash"
    assert attrs.get("gen_ai.system") == "google_vertex_ai"
    assert attrs.get("sdo.domain") == "finance"


@pytest.mark.asyncio
async def test_opentelemetry_graph_execution_spans():
    """Verify that SDOStateGraph steps automatically emit OpenTelemetry spans."""
    clear_in_memory_spans()

    state = LoopState(
        loop_id="01KZZGRAPHSPANS0000001",
        node_id="firmware",
        initiator=ActorIdentity(actor_type="human", user_email="firmware.eng@wallbox.com"),
        brief_raw="Aggregate charger error logs.",
    )

    graph = SDOStateGraph()
    graph.add_node("INTAKE", lambda s: s)
    graph.add_node("SPECIFY", lambda s: s)

    # Step INTAKE -> SPECIFY
    state = await graph.step(state)
    assert state.current_state == "SPECIFY"

    # Step SPECIFY -> SPEC_HARNESS
    state = await graph.step(state)
    assert state.current_state == "SPEC_HARNESS"

    spans = get_in_memory_spans()
    assert len(spans) >= 2

    # Check first span (INTAKE)
    intake_attrs = spans[0].attributes if hasattr(spans[0], "attributes") else {}
    assert intake_attrs.get("sdo.loop_id") == state.loop_id
    assert intake_attrs.get("gen_ai.request.model") == "gemini-3.7-flash"
    assert intake_attrs.get("sdo.node_name") == "INTAKE"

    # Check second span (SPECIFY)
    specify_attrs = spans[1].attributes if hasattr(spans[1], "attributes") else {}
    assert specify_attrs.get("sdo.loop_id") == state.loop_id
    assert specify_attrs.get("gen_ai.request.model") == "gemini-3.7-flash"
    assert specify_attrs.get("sdo.node_name") == "SPECIFY"


@pytest.mark.asyncio
async def test_bigquery_agent_analytics_logging():
    """Verify BigQuery Agent Analytics plugin logs structured session trace events."""
    analytics = BigQueryAgentAnalytics(
        project_id="managed-agent-504409",
        dataset_id="sdo_analytics",
        table_name="session_traces",
        use_mock=True,
    )

    loop_id = "01KZZBQTEST00000000001"

    # Log 3 state transition events
    await analytics.log_step_event(
        loop_id=loop_id,
        node_id="finance",
        step_name="INTAKE",
        duration_ms=120.5,
        input_tokens=250,
        output_tokens=100,
        status="SUCCESS",
        metadata={"domain": "finance"},
    )
    await analytics.log_step_event(
        loop_id=loop_id,
        node_id="finance",
        step_name="SPECIFY",
        duration_ms=640.2,
        input_tokens=1200,
        output_tokens=450,
        status="SUCCESS",
        metadata={"spec_id": "SPEC-FINANCE-001"},
    )
    await analytics.log_step_event(
        loop_id=loop_id,
        node_id="finance",
        step_name="SPEC_HARNESS",
        duration_ms=310.0,
        input_tokens=600,
        output_tokens=200,
        status="SUCCESS",
    )

    events = analytics.get_events_for_loop(loop_id)
    assert len(events) == 3

    assert events[0].loop_id == loop_id
    assert events[0].step_name == "INTAKE"
    assert events[0].model_name == "gemini-3.7-flash"
    assert events[0].duration_ms == 120.5

    assert events[1].step_name == "SPECIFY"
    assert events[1].input_tokens == 1200
    assert events[1].output_tokens == 450
    assert events[1].metadata["spec_id"] == "SPEC-FINANCE-001"

    assert events[2].step_name == "SPEC_HARNESS"
    assert events[2].status == "SUCCESS"
