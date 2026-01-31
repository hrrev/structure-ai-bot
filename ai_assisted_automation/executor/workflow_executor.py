import uuid
from typing import Any

from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.executor import step_executor
from ai_assisted_automation.graph.topological_sort import sort as topo_sort
from ai_assisted_automation.graph.validator import validate
from ai_assisted_automation.models.run import Run, RunStatus, StepResult, StepStatus
from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.models.workflow import Workflow


def execute(
    workflow: Workflow,
    user_inputs: dict[str, Any],
    tool_map: dict[str, ToolDefinition],
    tool_configs: dict[str, dict[str, str]] | None = None,
) -> Run:
    validate(workflow)
    tool_configs = tool_configs or {}

    state = StateManager()
    state.set_user_inputs(user_inputs)

    order = topo_sort(workflow)
    step_lookup = {s.id: s for s in workflow.steps}

    run = Run(
        id=str(uuid.uuid4()),
        workflow_id=workflow.id,
        status=RunStatus.RUNNING,
        user_inputs=user_inputs,
    )

    failed = False
    for step_id in order:
        if failed:
            run.step_results.append(
                StepResult(step_id=step_id, status=StepStatus.SKIPPED)
            )
            continue

        step = step_lookup[step_id]
        tool = tool_map[step.tool_id]
        result = step_executor.execute(
            step, tool, state, tool_configs.get(step.tool_id)
        )
        run.step_results.append(result)

        if result.status == StepStatus.FAILED:
            failed = True

    run.status = RunStatus.FAILED if failed else RunStatus.SUCCESS
    return run
