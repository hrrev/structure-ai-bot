from ai_assisted_automation.graph.edge_inference import infer_edges
from ai_assisted_automation.models.workflow import Edge, Step, Workflow


def _wf(steps, edges=None):
    return Workflow(id="w1", name="test", steps=steps, edges=edges or [])


class TestInferEdges:
    def test_infers_missing_edge(self):
        steps = [
            Step(id="s1", tool_id="t1"),
            Step(id="s2", tool_id="t2", input_mapping={"x": "s1.result"}),
        ]
        edges = infer_edges(_wf(steps))
        assert any(e.from_step_id == "s1" and e.to_step_id == "s2" for e in edges)

    def test_explicit_edge_preserved(self):
        steps = [
            Step(id="s1", tool_id="t1"),
            Step(id="s2", tool_id="t2", input_mapping={"x": "s1.result"}),
        ]
        explicit = [Edge(from_step_id="s1", to_step_id="s2")]
        edges = infer_edges(_wf(steps, explicit))
        # Should have exactly one edge, not duplicated
        s1_s2 = [e for e in edges if e.from_step_id == "s1" and e.to_step_id == "s2"]
        assert len(s1_s2) == 1

    def test_input_refs_ignored(self):
        steps = [
            Step(id="s1", tool_id="t1", input_mapping={"x": "$input.city"}),
        ]
        edges = infer_edges(_wf(steps))
        assert edges == []

    def test_literal_ignored(self):
        steps = [
            Step(id="s1", tool_id="t1", input_mapping={"x": "plain_literal"}),
        ]
        edges = infer_edges(_wf(steps))
        assert edges == []

    def test_multiple_deps_inferred(self):
        steps = [
            Step(id="s1", tool_id="t1"),
            Step(id="s2", tool_id="t2"),
            Step(id="s3", tool_id="t3", input_mapping={"a": "s1.x", "b": "s2.y"}),
        ]
        edges = infer_edges(_wf(steps))
        froms = {e.from_step_id for e in edges}
        assert froms == {"s1", "s2"}

    def test_no_self_edge(self):
        steps = [
            Step(id="s1", tool_id="t1", input_mapping={"x": "s1.prev"}),
        ]
        edges = infer_edges(_wf(steps))
        assert edges == []
