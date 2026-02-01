import uuid
from collections.abc import Callable
from datetime import datetime, timezone
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
    on_step_complete: Callable[[Run], None] | None = None,
    run_id: str | None = None,
) -> Run:
    validate(workflow)
    tool_configs = tool_configs or {}

    state = StateManager()
    state.set_user_inputs(user_inputs)

    order = topo_sort(workflow)
    step_lookup = {s.id: s for s in workflow.steps}

    run = Run(
        id=run_id or str(uuid.uuid4()),
        workflow_id=workflow.id,
        status=RunStatus.RUNNING,
        user_inputs=user_inputs,
        started_at=datetime.now(timezone.utc),
        step_results=[
            StepResult(step_id=sid, status=StepStatus.PENDING)
            for sid in order
        ],
    )

    if on_step_complete:
        on_step_complete(run)

    result_index = {sid: i for i, sid in enumerate(order)}

    failed = False
    for step_id in order:
        idx = result_index[step_id]

        if failed:
            run.step_results[idx].status = StepStatus.SKIPPED
            run.step_results[idx].finished_at = datetime.now(timezone.utc)
            if on_step_complete:
                on_step_complete(run)
            continue

        # Mark RUNNING
        run.step_results[idx].status = StepStatus.RUNNING
        run.step_results[idx].started_at = datetime.now(timezone.utc)
        if on_step_complete:
            on_step_complete(run)

        step = step_lookup[step_id]
        tool = tool_map[step.tool_id]
        result = step_executor.execute(
            step, tool, state, tool_configs.get(step.tool_id)
        )

        run.step_results[idx].status = result.status
        run.step_results[idx].output_data = result.output_data
        run.step_results[idx].error = result.error
        run.step_results[idx].finished_at = datetime.now(timezone.utc)

        if on_step_complete:
            on_step_complete(run)

        if result.status == StepStatus.FAILED:
            failed = True

    run.status = RunStatus.FAILED if failed else RunStatus.SUCCESS
    run.finished_at = datetime.now(timezone.utc)
    if on_step_complete:
        on_step_complete(run)
    return run
