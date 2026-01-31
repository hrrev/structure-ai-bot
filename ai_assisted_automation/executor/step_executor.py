from ai_assisted_automation.executor import api_client
from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.models.run import StepResult, StepStatus
from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.models.workflow import Step
from ai_assisted_automation.utils.exceptions import StepExecutionError


def execute(
    step: Step,
    tool: ToolDefinition,
    state_manager: StateManager,
    tool_config: dict | None = None,
) -> StepResult:
    try:
        resolved = state_manager.resolve_input_mapping(step.input_mapping)
        output = api_client.call(tool, resolved, tool_config)
        state_manager.store_step_output(step.id, output)
        return StepResult(step_id=step.id, status=StepStatus.SUCCESS, output_data=output)
    except (StepExecutionError, Exception) as e:
        return StepResult(step_id=step.id, status=StepStatus.FAILED, error=str(e))
