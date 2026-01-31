from enum import Enum
from typing import Any
from pydantic import BaseModel


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"


class StepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class StepResult(BaseModel):
    step_id: str
    status: StepStatus
    output_data: dict[str, Any] = {}
    error: str | None = None


class Run(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus
    step_results: list[StepResult] = []
    user_inputs: dict[str, Any] = {}
