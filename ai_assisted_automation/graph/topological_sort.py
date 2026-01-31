from collections import deque

from ai_assisted_automation.models.workflow import Workflow


def sort(workflow: Workflow) -> list[str]:
    in_degree: dict[str, int] = {s.id: 0 for s in workflow.steps}
    adj: dict[str, list[str]] = {s.id: [] for s in workflow.steps}

    for edge in workflow.edges:
        adj[edge.from_step_id].append(edge.to_step_id)
        in_degree[edge.to_step_id] += 1

    queue = deque(sorted(s_id for s_id, deg in in_degree.items() if deg == 0))
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in sorted(adj[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result
