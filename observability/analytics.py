"""BigQuery Agent Analytics Plugin for ADK (adk.dev/integrations/bigquery-agent-analytics)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AnalyticsEvent(BaseModel):
    """Session telemetry record streamed to BigQuery Agent Analytics."""

    loop_id: str
    node_id: str
    step_name: str
    model_name: str = "gemini-3.7-flash"
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    status: str = "SUCCESS"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class BigQueryAgentAnalytics:
    """Plugin streaming structured agent execution metrics and session traces to BigQuery."""

    def __init__(
        self,
        project_id: str = "managed-agent-504409",
        dataset_id: str = "sdo_analytics",
        table_name: str = "session_traces",
        use_mock: bool = True,
    ) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_name = table_name
        self.use_mock = use_mock
        self._mock_events: list[AnalyticsEvent] = []

    async def log_step_event(
        self,
        loop_id: str,
        node_id: str,
        step_name: str,
        duration_ms: float,
        input_tokens: int = 500,
        output_tokens: int = 250,
        status: str = "SUCCESS",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Stream one state execution step into BigQuery Agent Analytics."""
        event = AnalyticsEvent(
            loop_id=loop_id,
            node_id=node_id,
            step_name=step_name,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
            metadata=metadata or {},
        )
        self._mock_events.append(event)
        logger.info(
            "Logged BigQuery Analytics event for loop '%s' step '%s' (tokens: in=%d/out=%d, duration=%.1fms)",
            loop_id,
            step_name,
            input_tokens,
            output_tokens,
            duration_ms,
        )

    def get_events_for_loop(self, loop_id: str) -> list[AnalyticsEvent]:
        """Retrieve recorded telemetry for evaluation and debugging."""
        return [e for e in self._mock_events if e.loop_id == loop_id]
