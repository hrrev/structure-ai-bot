import threading
import tempfile
from pathlib import Path

import pytest

from ai_assisted_automation.models.run import Run, RunStatus, StepResult, StepStatus
from ai_assisted_automation.models.workflow import Workflow, Step, Edge
from ai_assisted_automation.storage.json_store import JsonStore


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path)


@pytest.fixture
def sample_workflow():
    return Workflow(
        id="wf1", name="Test Workflow",
        steps=[Step(id="s1", tool_id="t1"), Step(id="s2", tool_id="t2")],
        edges=[Edge(from_step_id="s1", to_step_id="s2")],
    )


@pytest.fixture
def sample_run():
    return Run(
        id="run1", workflow_id="wf1", status=RunStatus.RUNNING,
        step_results=[StepResult(step_id="s1", status=StepStatus.PENDING)],
    )


def test_save_load_workflow(store, sample_workflow):
    store.save_workflow(sample_workflow)
    loaded = store.load_workflow("wf1")
    assert loaded.id == "wf1"
    assert loaded.name == "Test Workflow"
    assert len(loaded.steps) == 2


def test_list_workflows(store, sample_workflow):
    store.save_workflow(sample_workflow)
    wf2 = Workflow(id="wf2", name="Second", steps=[Step(id="s1", tool_id="t1")])
    store.save_workflow(wf2)
    assert len(store.list_workflows()) == 2


def test_load_missing_workflow(store):
    with pytest.raises(FileNotFoundError):
        store.load_workflow("nonexistent")


def test_save_load_run(store, sample_run):
    store.save_run(sample_run)
    loaded = store.load_run("run1")
    assert loaded.id == "run1"
    assert loaded.status == RunStatus.RUNNING


def test_list_runs_filter(store, sample_run):
    store.save_run(sample_run)
    run2 = Run(id="run2", workflow_id="wf2", status=RunStatus.SUCCESS)
    store.save_run(run2)
    assert len(store.list_runs()) == 2
    assert len(store.list_runs("wf1")) == 1


def test_update_run(store, sample_run):
    store.save_run(sample_run)
    sample_run.status = RunStatus.SUCCESS
    store.update_run(sample_run)
    loaded = store.load_run("run1")
    assert loaded.status == RunStatus.SUCCESS


def test_load_missing_run(store):
    with pytest.raises(FileNotFoundError):
        store.load_run("nonexistent")


def test_concurrent_writes(store):
    """Multiple threads writing runs don't corrupt data."""
    errors = []

    def write_run(i):
        try:
            run = Run(id=f"run_{i}", workflow_id="wf1", status=RunStatus.SUCCESS)
            store.save_run(run)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write_run, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert not errors
    assert len(store.list_runs()) == 20
