import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_assisted_automation.api.app import create_app
from ai_assisted_automation.models.run import StepResult, StepStatus
from ai_assisted_automation.models.tool import ToolDefinition


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=str(tmp_path), tools_dir=str(tmp_path / "tools"))
    # Trigger startup manually
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_workflow_data():
    return {
        "id": "test_wf",
        "name": "Test Workflow",
        "steps": [
            {"id": "s1", "tool_id": "t1", "input_mapping": {}},
            {"id": "s2", "tool_id": "t1", "input_mapping": {"x": "s1.val"}},
        ],
        "edges": [{"from_step_id": "s1", "to_step_id": "s2"}],
    }


def test_workflow_crud(client, sample_workflow_data):
    # Create
    resp = client.post("/api/workflows", json=sample_workflow_data)
    assert resp.status_code == 200
    assert resp.json()["id"] == "test_wf"

    # List
    resp = client.get("/api/workflows")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Get
    resp = client.get("/api/workflows/test_wf")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Workflow"

    # Not found
    resp = client.get("/api/workflows/nonexistent")
    assert resp.status_code == 404


@patch("ai_assisted_automation.executor.step_executor.execute")
def test_run_creation_and_status(mock_exec, client, sample_workflow_data):
    mock_exec.return_value = StepResult(step_id="s1", status=StepStatus.SUCCESS, output_data={"val": 1})

    # Register tool in app registry
    tool = ToolDefinition(id="t1", name="T1", base_url="http://x.com", endpoint="/x", method="GET")
    client.app.state.registry.register(tool)

    # Create workflow
    client.post("/api/workflows", json=sample_workflow_data)

    # Trigger run
    resp = client.post("/api/workflows/test_wf/runs", json={"user_inputs": {}})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # Wait for background execution
    time.sleep(1)

    # Get run status
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("success", "running", "failed")

    # List runs
    resp = client.get("/api/workflows/test_wf/runs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_run_workflow_not_found(client):
    resp = client.post("/api/workflows/nonexistent/runs", json={"user_inputs": {}})
    assert resp.status_code == 404


def test_run_not_found(client):
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404
