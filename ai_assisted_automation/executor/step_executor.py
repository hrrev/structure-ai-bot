from ai_assisted_automation.executor import api_client
from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.executor.step_validator import validate_data
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
        all_warnings: list[str] = []

        # Input validations (before API call)
        if step.validations:
            input_result = validate_data(resolved, step.validations, "input")
            all_warnings.extend(input_result.warnings)
            if input_result.errors:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=f"Input validation failed: {'; '.join(input_result.errors)}",
                    warnings=all_warnings,
                )

        output = api_client.call(tool, resolved, tool_config)
        state_manager.store_step_output(step.id, output)

        # Output validations (after API call)
        if step.validations:
            output_result = validate_data(output, step.validations, "output")
            all_warnings.extend(output_result.warnings)
            if output_result.errors:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    output_data=output,
                    error=f"Output validation failed: {'; '.join(output_result.errors)}",
                    warnings=all_warnings,
                )

        return StepResult(step_id=step.id, status=StepStatus.SUCCESS, output_data=output, warnings=all_warnings)
    except (StepExecutionError, Exception) as e:
        return StepResult(step_id=step.id, status=StepStatus.FAILED, error=str(e))
