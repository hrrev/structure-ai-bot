from datetime import datetime
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
    RUNNING = "running"


class StepResult(BaseModel):
    step_id: str
    status: StepStatus
    output_data: dict[str, Any] = {}
    error: str | None = None
    warnings: list[str] = []
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Run(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus
    step_results: list[StepResult] = []
    user_inputs: dict[str, Any] = {}
    started_at: datetime | None = None
    finished_at: datetime | None = None
