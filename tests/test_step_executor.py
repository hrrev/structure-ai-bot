from unittest.mock import patch
from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.executor.step_executor import execute
from ai_assisted_automation.models.run import StepStatus
from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.models.workflow import Step
from ai_assisted_automation.utils.exceptions import StepExecutionError


def _tool():
    return ToolDefinition(id="t", name="test", base_url="http://example.com")


def test_successful_step():
    sm = StateManager()
    step = Step(id="s1", tool_id="t", input_mapping={})
    with patch("ai_assisted_automation.executor.api_client.call", return_value={"ok": True}):
        result = execute(step, _tool(), sm)
    assert result.status == StepStatus.SUCCESS
    assert result.output_data == {"ok": True}


def test_failed_step():
    sm = StateManager()
    step = Step(id="s1", tool_id="t", input_mapping={})
    with patch("ai_assisted_automation.executor.api_client.call", side_effect=StepExecutionError("boom")):
        result = execute(step, _tool(), sm)
    assert result.status == StepStatus.FAILED
    assert "boom" in result.error
