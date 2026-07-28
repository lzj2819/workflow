"""Trace 组装器"""

from datetime import datetime, timezone

from mock_framework.models.simulator import (
    ExecutionTrace,
    TraceStep,
    SideEffect,
    StateTransitionRecord,
)


class TraceAssembler:
    """Trace 组装器"""

    def assemble(
        self,
        test_case_id: str,
        trace_id: str,
        steps: list[TraceStep],
        side_effects: list[SideEffect],
        state_transitions: list[StateTransitionRecord],
    ) -> ExecutionTrace:
        """组装 ExecutionTrace"""
        now = datetime.now(timezone.utc)
        total_latency = sum(s.latency_ms for s in steps)

        return ExecutionTrace(
            trace_id=trace_id,
            test_case_id=test_case_id,
            start_time=now,
            end_time=now,
            total_latency_ms=total_latency,
            steps=steps,
            side_effects=side_effects,
            state_transitions=state_transitions,
        )
