import queue
import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_assisted_automation.api import sse
from ai_assisted_automation.executor import workflow_executor
from ai_assisted_automation.models.run import Run, RunStatus, StepResult, StepStatus
from ai_assisted_automation.models.workflow import Workflow

router = APIRouter(prefix="/api")


class RunRequest(BaseModel):
    user_inputs: dict[str, Any] = {}


# --- Workflows ---

@router.get("/workflows")
def list_workflows(request: Request):
    store = request.app.state.store
    return [w.model_dump(mode="json") for w in store.list_workflows()]


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, request: Request):
    store = request.app.state.store
    try:
        return store.load_workflow(workflow_id).model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")


@router.post("/workflows")
def create_workflow(workflow: Workflow, request: Request):
    store = request.app.state.store
    store.save_workflow(workflow)
    return {"id": workflow.id}


# --- Runs ---

@router.get("/workflows/{workflow_id}/runs")
def list_runs(workflow_id: str, request: Request):
    store = request.app.state.store
    return [r.model_dump(mode="json") for r in store.list_runs(workflow_id)]


@router.post("/workflows/{workflow_id}/runs")
def create_run(workflow_id: str, body: RunRequest, request: Request):
    store = request.app.state.store
    registry = request.app.state.registry
    tool_configs = request.app.state.tool_configs

    try:
        workflow = store.load_workflow(workflow_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")

    tool_map = {}
    for step in workflow.steps:
        try:
            tool = registry.get_tool(step.tool_id)
        except KeyError:
            raise HTTPException(400, f"Tool '{step.tool_id}' not registered")
        tool_map[step.tool_id] = tool

    run_id = str(uuid.uuid4())

    def run_in_background():
        def on_step_complete(run: Run):
            store.update_run(run)
            sse.notify(run_id, run.model_dump(mode="json"))

        try:
            run = workflow_executor.execute(
                workflow=workflow,
                user_inputs=body.user_inputs,
                tool_map=tool_map,
                tool_configs=tool_configs,
                on_step_complete=on_step_complete,
                run_id=run_id,
            )
        except Exception as e:
            from datetime import datetime, timezone
            run = Run(
                id=run_id, workflow_id=workflow_id,
                status=RunStatus.FAILED,
                user_inputs=body.user_inputs,
                step_results=[],
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        store.update_run(run)
        sse.notify(run_id, {**run.model_dump(mode="json"), "done": True})
        sse.complete(run_id)

    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return {"run_id": run_id}


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request):
    store = request.app.state.store
    try:
        return store.load_run(run_id).model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(404, f"Run '{run_id}' not found")


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str):
    import json

    q = sse.subscribe(run_id)

    def event_generator():
        while True:
            try:
                data = q.get(timeout=30)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if data is None:
                return
            yield f"data: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
