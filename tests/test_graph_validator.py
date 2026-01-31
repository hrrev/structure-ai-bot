import pytest
from ai_assisted_automation.models.workflow import Workflow, Step, Edge
from ai_assisted_automation.graph.validator import validate
from ai_assisted_automation.utils.exceptions import WorkflowValidationError


def _make_workflow(steps, edges):
    return Workflow(id="w1", name="test", steps=steps, edges=edges)


def test_valid_linear_dag():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"), Step(id="C", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="B", to_step_id="C")],
    )
    validate(w)


def test_valid_diamond_dag():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"),
         Step(id="C", tool_id="t"), Step(id="D", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="A", to_step_id="C"),
         Edge(from_step_id="B", to_step_id="D"), Edge(from_step_id="C", to_step_id="D")],
    )
    validate(w)


def test_cycle_detected():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="B", to_step_id="A")],
    )
    with pytest.raises(WorkflowValidationError, match="Cycle"):
        validate(w)


def test_invalid_edge_reference():
    w = _make_workflow(
        [Step(id="A", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="Z")],
    )
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        validate(w)


def test_invalid_input_mapping_reference():
    w = _make_workflow(
        [Step(id="A", tool_id="t"),
         Step(id="B", tool_id="t", input_mapping={"x": "Z.field"})],
        [Edge(from_step_id="A", to_step_id="B")],
    )
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        validate(w)


def test_single_node():
    w = _make_workflow([Step(id="A", tool_id="t")], [])
    validate(w)


def test_input_mapping_non_predecessor_raises():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"),
         Step(id="C", tool_id="t", input_mapping={"x": "B.field"})],
        [Edge(from_step_id="A", to_step_id="C")],
    )
    with pytest.raises(WorkflowValidationError, match="not a predecessor"):
        validate(w)
