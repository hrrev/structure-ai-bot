from unittest.mock import patch
from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.run import RunStatus, StepStatus
from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.models.workflow import Workflow, Step, Edge, StepSeverity
from ai_assisted_automation.utils.exceptions import StepExecutionError


def _tool():
    return ToolDefinition(id="t", name="test", base_url="http://example.com")


def test_linear_all_succeed():
    w = Workflow(
        id="w1", name="test",
        steps=[
            Step(id="A", tool_id="t", input_mapping={"name": "$input.name"}),
            Step(id="B", tool_id="t", input_mapping={"aid": "A.account_id"}),
        ],
        edges=[Edge(from_step_id="A", to_step_id="B")],
    )
    call_results = iter([{"account_id": "123"}, {"done": True}])
    with patch("ai_assisted_automation.executor.api_client.call", side_effect=lambda *a, **kw: next(call_results)):
        run = execute(w, {"name": "Alice"}, {"t": _tool()})
    assert run.status == RunStatus.SUCCESS
    assert len(run.step_results) == 2
    assert all(r.status == StepStatus.SUCCESS for r in run.step_results)


def test_mid_failure_skips_rest():
    w = Workflow(
        id="w1", name="test",
        steps=[
            Step(id="A", tool_id="t"),
            Step(id="B", tool_id="t"),
            Step(id="C", tool_id="t"),
        ],
        edges=[Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="B", to_step_id="C")],
    )

    def side_effect(*a, **kw):
        if side_effect.count == 0:
            side_effect.count += 1
            return {"ok": True}
        raise StepExecutionError("fail")
    side_effect.count = 0

    with patch("ai_assisted_automation.executor.api_client.call", side_effect=side_effect):
        run = execute(w, {}, {"t": _tool()})
    assert run.status == RunStatus.FAILED
    assert run.step_results[0].status == StepStatus.SUCCESS
    assert run.step_results[1].status == StepStatus.FAILED
    assert run.step_results[2].status == StepStatus.SKIPPED


def test_user_inputs_passed():
    w = Workflow(
        id="w1", name="test",
        steps=[Step(id="A", tool_id="t", input_mapping={"email": "$input.email"})],
    )
    with patch("ai_assisted_automation.executor.api_client.call", return_value={"ok": True}) as mock_call:
        execute(w, {"email": "a@b.com"}, {"t": _tool()})
    resolved_inputs = mock_call.call_args[0][1]
    assert resolved_inputs["email"] == "a@b.com"


def test_non_critical_step_failure_continues_graph():
    """Non-critical step fails → non-dependent steps still execute → run status SUCCESS."""
    w = Workflow(
        id="w1", name="test",
        steps=[
            Step(id="A", tool_id="t"),
            Step(id="B", tool_id="t", severity=StepSeverity.NON_CRITICAL),
            Step(id="C", tool_id="t"),
        ],
        edges=[],  # A, B, C are independent
    )

    call_count = 0
    def side_effect(*a, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # B is second in topo order (sorted alphabetically)
            raise StepExecutionError("non-critical fail")
        return {"ok": True}

    with patch("ai_assisted_automation.executor.api_client.call", side_effect=side_effect):
        run = execute(w, {}, {"t": _tool()})
    assert run.status == RunStatus.SUCCESS
    assert run.step_results[0].status == StepStatus.SUCCESS  # A
    assert run.step_results[1].status == StepStatus.FAILED   # B
    assert run.step_results[2].status == StepStatus.SUCCESS   # C


def test_non_critical_step_failure_skips_dependents():
    """Non-critical step fails → its dependents are skipped → parallel branch continues."""
    w = Workflow(
        id="w1", name="test",
        steps=[
            Step(id="A", tool_id="t", severity=StepSeverity.NON_CRITICAL),
            Step(id="B", tool_id="t"),  # depends on A
            Step(id="C", tool_id="t"),  # independent
        ],
        edges=[Edge(from_step_id="A", to_step_id="B")],
    )

    def side_effect(*a, **kw):
        if side_effect.count == 0:
            side_effect.count += 1
            raise StepExecutionError("non-critical fail")
        return {"ok": True}
    side_effect.count = 0

    with patch("ai_assisted_automation.executor.api_client.call", side_effect=side_effect):
        run = execute(w, {}, {"t": _tool()})
    assert run.status == RunStatus.SUCCESS
    # Topo order: A, C, B (C is independent, sorted before B which has in-degree 1)
    results = {r.step_id: r.status for r in run.step_results}
    assert results["A"] == StepStatus.FAILED
    assert results["B"] == StepStatus.SKIPPED   # depends on A
    assert results["C"] == StepStatus.SUCCESS    # independent


def test_critical_step_failure_marks_graph_failed():
    """Critical step fails → dependents skip, graph FAILED (backward compat)."""
    w = Workflow(
        id="w1", name="test",
        steps=[
            Step(id="A", tool_id="t"),  # default severity = CRITICAL
            Step(id="B", tool_id="t"),  # depends on A
            Step(id="C", tool_id="t"),  # independent
        ],
        edges=[Edge(from_step_id="A", to_step_id="B")],
    )

    def side_effect(*a, **kw):
        if side_effect.count == 0:
            side_effect.count += 1
            raise StepExecutionError("critical fail")
        return {"ok": True}
    side_effect.count = 0

    with patch("ai_assisted_automation.executor.api_client.call", side_effect=side_effect):
        run = execute(w, {}, {"t": _tool()})
    assert run.status == RunStatus.FAILED
    results = {r.step_id: r.status for r in run.step_results}
    assert results["A"] == StepStatus.FAILED
    assert results["B"] == StepStatus.SKIPPED   # depends on A
    assert results["C"] == StepStatus.SUCCESS    # independent, still runs
