"""SDO Platform ADK State Graph Assembly and Execution Engine."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Coroutine
from graphs.state import LoopState
from graphs.router import route_spec_harness, route_gate_h1, route_review, route_gate_h2
from observability.otel import trace_agent_step

logger = logging.getLogger(__name__)

# Type definition for sync or async node execution functions
NodeHandler = Callable[[LoopState], Coroutine[Any, Any, LoopState] | LoopState]


class SDOStateGraph:
    """Deterministic State Graph engine implementing the ADK 2.0 graph contract."""

    def __init__(self) -> None:
        self.nodes: dict[str, NodeHandler] = {}
        self.entry_point: str = "INTAKE"

    def add_node(self, name: str, handler: NodeHandler) -> None:
        """Register a graph node handler."""
        self.nodes[name] = handler

    async def step(self, state: LoopState) -> LoopState:
        """Execute one step in the state graph and apply deterministic routing."""
        current = state.current_state
        logger.info("Executing node '%s' for loop '%s'", current, state.loop_id)

        if current not in self.nodes:
            raise ValueError(f"Node '{current}' is not registered in the state graph.")

        # Execute node logic wrapped with OpenTelemetry tracing
        handler = self.nodes[current]
        with trace_agent_step(
            node_name=current,
            loop_id=state.loop_id,
            attributes={
                "sdo.domain": state.node_id,
                "sdo.node_id": state.node_id,
                "sdo.current_state": current,
            },
        ):
            result = handler(state)
            if inspect.isawaitable(result):
                state = await result
            else:
                state = result  # type: ignore

        # If handler explicitly transitioned the state, honor that transition
        if state.current_state != current:
            logger.info("Transitioned loop '%s' to '%s' (by node handler)", state.loop_id, state.current_state)
            return state

        # Deterministic Next State Routing
        if current == "INTAKE":
            state.current_state = "SPECIFY"
        elif current == "SPECIFY":
            state.current_state = "SPEC_HARNESS"
        elif current == "SPEC_HARNESS":
            next_state = route_spec_harness(state)
            state.current_state = next_state
        elif current == "GATE_H1":
            next_state = route_gate_h1(state)
            state.current_state = next_state
        elif current == "DESIGN":
            state.current_state = "IMPLEMENT"
        elif current == "IMPLEMENT":
            state.current_state = "REVIEW"
        elif current == "REVIEW":
            next_state = route_review(state)
            state.current_state = next_state
        elif current == "GATE_H2":
            next_state = route_gate_h2(state)
            state.current_state = next_state
        elif current == "CLOSE":
            state.current_state = "WATCH"
        elif current == "WATCH":
            state.current_state = "DONE"
        elif current in ("DONE", "CLOSED", "ESCALATED", "WAIT_GATE_H1", "WAIT_GATE_H2"):
            pass  # Terminal or waiting states
        else:
            raise ValueError(f"Unhandled state transition from '{current}'.")

        logger.info("Transitioned loop '%s' to '%s'", state.loop_id, state.current_state)
        return state

    async def run_until_pause_or_terminal(self, state: LoopState, max_steps: int = 25) -> LoopState:
        """Execute steps sequentially until a human gate pause or terminal state is reached."""
        step_count = 0
        pause_or_terminal_states = {"WAIT_GATE_H1", "WAIT_GATE_H2", "DONE", "CLOSED", "ESCALATED"}

        while state.current_state not in pause_or_terminal_states and step_count < max_steps:
            state = await self.step(state)
            step_count += 1

        if step_count >= max_steps and state.current_state not in pause_or_terminal_states:
            state.current_state = "ESCALATED"
            state.escalation_reason = f"Execution exceeded maximum step limit ({max_steps}) without reaching terminal state."

        return state
