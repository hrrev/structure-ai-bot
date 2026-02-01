from unittest.mock import patch, MagicMock

import pytest

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.run import Run, RunStatus, StepStatus, StepResult
from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.models.workflow import Workflow, Step, Edge


@pytest.fixture
def simple_workflow():
    return Workflow(
        id="wf1", name="Test",
        steps=[Step(id="s1", tool_id="t1"), Step(id="s2", tool_id="t2")],
        edges=[Edge(from_step_id="s1", to_step_id="s2")],
    )


@pytest.fixture
def tool_map():
    t1 = ToolDefinition(id="t1", name="T1", base_url="http://a.com", endpoint="/a", method="GET")
    t2 = ToolDefinition(id="t2", name="T2", base_url="http://b.com", endpoint="/b", method="GET")
    return {"t1": t1, "t2": t2}


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_callback_called_for_each_transition(mock_exec, simple_workflow, tool_map):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={"x": 1})

    callbacks = []
    def on_step(run):
        statuses = {r.step_id: r.status for r in run.step_results}
        callbacks.append(dict(statuses))

    execute(simple_workflow, {}, tool_map, on_step_complete=on_step)

    # Initial (all PENDING), s1 RUNNING, s1 SUCCESS, s2 RUNNING, s2 SUCCESS, final
    assert len(callbacks) >= 6
    # First callback: all pending
    assert callbacks[0]["s1"] == StepStatus.PENDING
    assert callbacks[0]["s2"] == StepStatus.PENDING


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_steps_prepopulated_as_pending(mock_exec, simple_workflow, tool_map):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={})

    first_callback_run = []
    def on_step(run):
        if not first_callback_run:
            first_callback_run.append(run.model_copy(deep=True))

    execute(simple_workflow, {}, tool_map, on_step_complete=on_step)
    run = first_callback_run[0]
    assert len(run.step_results) == 2
    assert all(r.status == StepStatus.PENDING for r in run.step_results)


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_timestamps_set(mock_exec, simple_workflow, tool_map):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={})

    run = execute(simple_workflow, {}, tool_map)

    assert run.started_at is not None
    assert run.finished_at is not None
    for r in run.step_results:
        assert r.finished_at is not None


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_run_id_parameter(mock_exec, simple_workflow, tool_map):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={})

    run = execute(simple_workflow, {}, tool_map, run_id="custom-id")
    assert run.id == "custom-id"


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_no_callback_backward_compat(mock_exec, simple_workflow, tool_map):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={})

    run = execute(simple_workflow, {}, tool_map)
    assert run.status == RunStatus.SUCCESS
    assert len(run.step_results) == 2
