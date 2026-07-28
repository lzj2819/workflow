"""Validator Agent Core - LLM driven validation agent."""

import json
from typing import Optional

from mock_framework.models.arch import ArchDoc
from mock_framework.models.loader import TestCase
from mock_framework.models.simulator import ExecutionTrace
from mock_framework.simulator.llm_client import LLMClient, TokenBudgetExceeded


class ValidatorAgentCore:
    """LLM driven validation agent that performs 5-dimension validation."""

    def __init__(self, llm_client: LLMClient, token_budget: int = 2000) -> None:
        """Initialize ValidatorAgentCore.

        Args:
            llm_client: LLM client for making completion calls.
            token_budget: Maximum tokens allowed per scene (default 2000).
        """
        self.llm_client = llm_client
        self.token_budget = token_budget

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text.

        Uses a simple heuristic: len(text) // 4.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def _build_prompt(self, trace: ExecutionTrace, test_case: TestCase, arch_doc: ArchDoc) -> str:
        """Build the full validation prompt.

        Args:
            trace: Execution trace from the simulator.
            test_case: Test case with expectations.
            arch_doc: Architecture document with NFRs and constraints.

        Returns:
            The complete validation prompt string.
        """
        # Trace summary: keep only fields the validator actually needs to judge.
        trace_summary = {
            "trace_id": trace.trace_id,
            "test_case_id": trace.test_case_id,
            "total_latency_ms": trace.total_latency_ms,
            "steps": [
                {
                    "step_number": s.step_number,
                    "phase": s.phase,
                    "component": s.component,
                    "action": s.action,
                    "target": s.target,
                    "input": s.input,
                    "output": s.output,
                    "self_check": s.self_check,
                    "next_hop": s.next_hop,
                    "status": s.status,
                    "latency_ms": s.latency_ms,
                }
                for s in trace.steps
            ],
            "side_effects": [
                {"type": se.type, "target": se.target, "data": se.data} for se in trace.side_effects
            ],
            "state_transitions": [
                {
                    "entity": st.entity,
                    "from_state": st.from_state,
                    "to_state": st.to_state,
                    "trigger": st.trigger,
                }
                for st in trace.state_transitions
            ],
            "then_verifications": trace.then_verifications,
        }

        # Gherkin expectations: keep the scenario steps and explicit expectations only.
        gherkin_expectations = {
            "source_feature": test_case.source_feature,
            "scenario": test_case.gherkin.get("scenario", ""),
            "steps": test_case.gherkin.get("steps", []),
            "expectations": {
                "status_code": test_case.expectations.status_code,
                "response_schema": test_case.expectations.response_schema,
                "touched_components": test_case.expectations.touched_components,
                "side_effects": test_case.expectations.side_effects,
                "performance": test_case.expectations.performance,
            },
        }

        # NFRs
        nfrs_list = [
            {"id": nfr.id, "metric": nfr.metric, "threshold": nfr.threshold, "unit": nfr.unit}
            for nfr in arch_doc.nfrs
        ]

        # Components: only include components actually referenced in the trace or expectations.
        # This significantly shortens the prompt for large architectures.
        touched: set[str] = set()
        touched.update(test_case.expectations.touched_components)
        for s in trace.steps:
            touched.add(s.component)
            if s.target:
                touched.add(s.target)
        for tv in trace.then_verifications:
            comp = tv.get("component")
            if comp:
                touched.add(comp)
        for se in trace.side_effects:
            # Side-effect targets may be storage names like "session_state"; try exact match first.
            for comp in arch_doc.components:
                if comp.name in se.target or se.target in comp.name:
                    touched.add(comp.name)

        relevant_components = [c for c in arch_doc.components if c.name in touched]
        if not relevant_components:
            relevant_components = list(arch_doc.components)

        components_list = [
            {"name": c.name, "responsibility": c.responsibility} for c in relevant_components
        ]

        prompt = f"""You are a Validator Agent. Validate the simulator trace against the Gherkin scenario and architecture constraints.

## 1. Simulator Execution Result
```json
{json.dumps(trace_summary, indent=2, default=str, ensure_ascii=False)}
```

## 2. Gherkin Expected Behavior
```json
{json.dumps(gherkin_expectations, indent=2, default=str, ensure_ascii=False)}
```

## 3. Architecture Constraints
### NFRs
```json
{json.dumps(nfrs_list, indent=2, default=str, ensure_ascii=False)}
```

### Relevant Components
```json
{json.dumps(components_list, indent=2, default=str, ensure_ascii=False)}
```

## 4. VAL Rules
Evaluate across five dimensions. Be strict: require concrete evidence in the trace; do not accept plausible stories without proof.

1. **structure**: Required Gherkin phases (given/when/then) must be present and in order. If the trace's steps are all labeled `when` but the first step clearly establishes the Given precondition and the final step produces the Then outcome, do not fail structure solely for missing phase labels.
2. **flow**: Component interactions must match the architecture data flow; next_hop decisions must be justified.
3. **state**: State transitions must match the state machine and be owned by the correct component.
4. **contract**: API contracts (status codes, schemas, produced_fields, then_verifications) must match expectations. If `then_verifications` is empty but the final `output_message` and `side_effects` provide concrete evidence that the Then step is satisfied, judge contract based on that evidence rather than failing for the missing field.
5. **performance**: Latency must be within NFR thresholds or reasonable defaults.

Judgment: PASS=all dimensions pass; FAIL=any dimension fails; WARNING=no failures but warnings exist; MISSING=insufficient data.

## 5. Output Format
Return a single raw JSON object (no markdown):

{{
  "structure": {{"status": "PASS|FAIL|WARNING|MISSING", "detail": "..."}},
  "flow": {{"status": "PASS|FAIL|WARNING|MISSING", "detail": "..."}},
  "state": {{"status": "PASS|FAIL|WARNING|MISSING", "detail": "..."}},
  "contract": {{"status": "PASS|FAIL|WARNING|MISSING", "detail": "..."}},
  "performance": {{"status": "PASS|FAIL|WARNING|MISSING", "detail": "..."}},
  "overall": "PASS|FAIL|WARNING|MISSING",
  "failure_analysis": {{"dimension": "...", "problem": "...", "severity": "high|medium|low", "impact": "...", "suggestion": "...", "scope": "top_level|module"}},
  "warning_analysis": {{"dimension": "...", "problem": "...", "suggestion": "...", "scope": "top_level|module"}}
}}

Include failure_analysis for FAIL, warning_analysis for WARNING, omit both for PASS.

When deciding the optional "scope" field, use this rule:
- "top_level": the issue is caused by the architecture document missing a necessary design element at the current layer (missing component, wrong component responsibility, missing data flow, missing core state/lifecycle, missing major branch).
- "module": the document already declares the relevant element but the concrete details are insufficient (field names, copy text, algorithm, naming, sub-state, internal validation rule).
If you are unsure, omit "scope" and the framework will apply deterministic fallback rules.
"""
        return prompt

    def validate(self, trace: ExecutionTrace, test_case: TestCase, arch_doc: ArchDoc) -> dict:
        """Validate an execution trace against a test case and architecture doc.

        Builds the validation prompt, checks token budget, calls LLM,
        and parses the JSON response.

        Args:
            trace: Execution trace from the simulator.
            test_case: Test case with expectations.
            arch_doc: Architecture document with NFRs and constraints.

        Returns:
            Parsed dict from the LLM JSON response.

        Raises:
            TokenBudgetExceeded: If the prompt exceeds the token budget.
        """
        prompt = self._build_prompt(trace, test_case, arch_doc)
        estimated = self._estimate_tokens(prompt)
        if estimated > self.token_budget:
            raise TokenBudgetExceeded(
                f"Token budget exceeded: estimated {estimated} > budget {self.token_budget}"
            )

        response = self.llm_client.complete(prompt)

        # LLMClient returns parsed JSON directly.
        # If it already contains validation dimensions, return as-is.
        if "structure" in response and "flow" in response:
            return response

        # If wrapped in 'raw' (plain text fallback), extract JSON from it.
        content = response.get("raw", "")
        if not content:
            content = response.get("content", "")
        if not content:
            raise ValueError("LLM response missing 'content' or 'raw' field")

        # Try to parse JSON directly; if that fails, try to extract JSON from markdown
        result: dict
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Attempt to extract JSON from markdown code blocks
            import re

            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if match:
                result = json.loads(match.group(1).strip())
            else:
                raise ValueError(f"LLM response is not valid JSON: {content}")

        return result
