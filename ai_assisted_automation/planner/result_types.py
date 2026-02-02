"""Pydantic models for LLM planner structured output."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PlannedStep(BaseModel):
    """A single step in the planned workflow."""

    id: str
    tool_id: str
    name: str
    description: str
    input_mapping: dict[str, str]
    severity: str = "critical"


class PlannedEdge(BaseModel):
    """An explicit edge between two steps."""

    from_step_id: str
    to_step_id: str


class PlanSuccess(BaseModel):
    """LLM successfully planned a workflow."""

    kind: Literal["plan"] = "plan"
    workflow_name: str
    steps: list[PlannedStep]
    edges: list[PlannedEdge] = []
    required_user_inputs: list[str]


class InsufficientTools(BaseModel):
    """Available tools cannot accomplish the goal."""

    kind: Literal["insufficient_tools"] = "insufficient_tools"
    reason: str
    missing_capabilities: list[str]


PlanResult = Annotated[
    PlanSuccess | InsufficientTools,
    Field(discriminator="kind"),
]
