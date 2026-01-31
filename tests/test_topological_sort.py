from ai_assisted_automation.models.workflow import Workflow, Step, Edge
from ai_assisted_automation.graph.topological_sort import sort


def _make_workflow(steps, edges):
    return Workflow(id="w1", name="test", steps=steps, edges=edges)


def test_linear():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"), Step(id="C", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="B", to_step_id="C")],
    )
    assert sort(w) == ["A", "B", "C"]


def test_diamond():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"),
         Step(id="C", tool_id="t"), Step(id="D", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="B"), Edge(from_step_id="A", to_step_id="C"),
         Edge(from_step_id="B", to_step_id="D"), Edge(from_step_id="C", to_step_id="D")],
    )
    result = sort(w)
    assert result[0] == "A"
    assert result[-1] == "D"
    assert set(result[1:3]) == {"B", "C"}


def test_single_node():
    w = _make_workflow([Step(id="A", tool_id="t")], [])
    assert sort(w) == ["A"]


def test_parallel_roots():
    w = _make_workflow(
        [Step(id="A", tool_id="t"), Step(id="B", tool_id="t"), Step(id="C", tool_id="t")],
        [Edge(from_step_id="A", to_step_id="C"), Edge(from_step_id="B", to_step_id="C")],
    )
    result = sort(w)
    assert result[-1] == "C"
    assert set(result[:2]) == {"A", "B"}
