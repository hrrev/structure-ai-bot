from enum import Enum
from pydantic import BaseModel


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class Step(BaseModel):
    id: str
    tool_id: str
    input_mapping: dict[str, str] = {}
    description: str = ""


class Edge(BaseModel):
    from_step_id: str
    to_step_id: str


class Workflow(BaseModel):
    id: str
    name: str
    steps: list[Step]
    edges: list[Edge] = []
    status: WorkflowStatus = WorkflowStatus.DRAFT
