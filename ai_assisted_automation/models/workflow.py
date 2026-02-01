from enum import Enum
from pydantic import BaseModel


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class StepValidation(BaseModel):
    field: str
    check: str  # not_null, not_empty, min_length, regex, type
    target: str = "output"  # "output" or "input"
    value: str | None = None  # param for checks that need it
    message: str = ""  # optional custom error message
    critical: bool = True  # False = warning only, doesn't fail the step


class StepSeverity(str, Enum):
    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"


class Step(BaseModel):
    id: str
    tool_id: str
    input_mapping: dict[str, str] = {}
    description: str = ""
    name: str = ""
    validations: list[StepValidation] = []
    severity: StepSeverity = StepSeverity.CRITICAL


class Edge(BaseModel):
    from_step_id: str
    to_step_id: str


class Workflow(BaseModel):
    id: str
    name: str
    steps: list[Step]
    edges: list[Edge] = []
    status: WorkflowStatus = WorkflowStatus.DRAFT
