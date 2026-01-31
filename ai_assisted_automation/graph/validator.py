from ai_assisted_automation.models.workflow import Workflow
from ai_assisted_automation.utils.exceptions import WorkflowValidationError


def validate(workflow: Workflow) -> None:
    _check_valid_step_references(workflow)
    _check_no_cycles(workflow)
    _check_input_mappings(workflow)


def _check_valid_step_references(workflow: Workflow) -> None:
    step_ids = {s.id for s in workflow.steps}
    for edge in workflow.edges:
        if edge.from_step_id not in step_ids:
            raise WorkflowValidationError(
                f"Edge references unknown step: {edge.from_step_id}"
            )
        if edge.to_step_id not in step_ids:
            raise WorkflowValidationError(
                f"Edge references unknown step: {edge.to_step_id}"
            )


def _check_no_cycles(workflow: Workflow) -> None:
    adj: dict[str, list[str]] = {s.id: [] for s in workflow.steps}
    for edge in workflow.edges:
        adj[edge.from_step_id].append(edge.to_step_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s.id: WHITE for s in workflow.steps}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adj[node]:
            if color[neighbor] == GRAY:
                raise WorkflowValidationError("Cycle detected in workflow")
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for step in workflow.steps:
        if color[step.id] == WHITE:
            dfs(step.id)


def _check_input_mappings(workflow: Workflow) -> None:
    step_ids = {s.id for s in workflow.steps}
    adj: dict[str, set[str]] = {s.id: set() for s in workflow.steps}
    for edge in workflow.edges:
        adj[edge.from_step_id].add(edge.to_step_id)

    # Build set of predecessors for each step
    predecessors: dict[str, set[str]] = {s.id: set() for s in workflow.steps}

    def _collect_predecessors(node: str, visited: set[str]) -> set[str]:
        result: set[str] = set()
        for s in workflow.steps:
            for edge in workflow.edges:
                if edge.to_step_id == node and edge.from_step_id not in visited:
                    result.add(edge.from_step_id)
                    visited.add(edge.from_step_id)
                    result |= _collect_predecessors(edge.from_step_id, visited)
        return result

    for step in workflow.steps:
        predecessors[step.id] = _collect_predecessors(step.id, set())

    for step in workflow.steps:
        for key, value in step.input_mapping.items():
            if value.startswith("$input."):
                continue
            if "." in value:
                ref_step = value.split(".")[0]
                if ref_step not in step_ids:
                    raise WorkflowValidationError(
                        f"Step {step.id} input_mapping references unknown step: {ref_step}"
                    )
                if ref_step not in predecessors[step.id]:
                    raise WorkflowValidationError(
                        f"Step {step.id} references step {ref_step} which is not a predecessor"
                    )
