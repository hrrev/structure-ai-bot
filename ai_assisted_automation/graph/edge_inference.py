"""Infer edges from step input_mappings to fill gaps left by the planner."""

import re

from ai_assisted_automation.models.workflow import Edge, Workflow

_STEP_REF_RE = re.compile(r"^(?!\$input\.)([a-zA-Z_]\w*)\..*$")


def infer_edges(workflow: Workflow) -> list[Edge]:
    """Return merged list of explicit + inferred edges (deduplicated)."""
    step_ids = {s.id for s in workflow.steps}
    existing = {(e.from_step_id, e.to_step_id) for e in workflow.edges}

    inferred: set[tuple[str, str]] = set()
    for step in workflow.steps:
        for value in step.input_mapping.values():
            m = _STEP_REF_RE.match(value)
            if m:
                ref = m.group(1)
                if ref in step_ids and ref != step.id:
                    pair = (ref, step.id)
                    if pair not in existing:
                        inferred.add(pair)

    merged = list(workflow.edges)
    for from_id, to_id in sorted(inferred):
        merged.append(Edge(from_step_id=from_id, to_step_id=to_id))
    return merged
