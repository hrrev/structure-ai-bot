"""Core LLM planner: goal + tool registry -> validated Workflow."""

import uuid
from typing import Any

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider

# # OpenAI support (uncomment to enable):
# from pydantic_ai.models.openai import OpenAIModel
# from pydantic_ai.providers.openai import OpenAIProvider

from ai_assisted_automation.config.settings import LLMConfig, Settings, load_settings
from ai_assisted_automation.graph.validator import validate
from ai_assisted_automation.models.workflow import Edge, Step, StepSeverity, Workflow, WorkflowStatus
from ai_assisted_automation.planner.prompt import build_system_prompt
from ai_assisted_automation.planner.result_types import InsufficientTools, PlanResult, PlanSuccess
from ai_assisted_automation.registry.tool_registry import ToolRegistry
from ai_assisted_automation.utils.exceptions import WorkflowValidationError


def _make_model(config: LLMConfig) -> Any:
    """Create a pydantic-ai model from config."""
    if config.provider == "anthropic":
        provider_kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.host_url:
            provider_kwargs["base_url"] = config.host_url
        return AnthropicModel(
            config.model,
            provider=AnthropicProvider(**provider_kwargs),
        )

    # # OpenAI support (uncomment to enable):
    # if config.provider == "openai":
    #     provider_kwargs: dict[str, Any] = {"api_key": config.api_key}
    #     if config.host_url:
    #         provider_kwargs["base_url"] = config.host_url
    #     return OpenAIModel(
    #         config.model,
    #         provider=OpenAIProvider(**provider_kwargs),
    #     )

    raise ValueError(f"Unknown LLM provider: {config.provider}")


def _make_model_settings(config: LLMConfig) -> AnthropicModelSettings | dict[str, Any]:
    """Create model settings with thinking enabled for Anthropic."""
    if config.provider == "anthropic":
        settings_kwargs: dict[str, Any] = {"max_tokens": config.max_tokens}
        if config.thinking_budget > 0:
            settings_kwargs["anthropic_thinking"] = {
                "type": "enabled",
                "budget_tokens": config.thinking_budget,
            }
        return AnthropicModelSettings(**settings_kwargs)
    return {"max_tokens": config.max_tokens}


async def plan(
    goal: str,
    registry: ToolRegistry,
    max_retries: int = 3,
    settings: Settings | None = None,
) -> Workflow | InsufficientTools:
    """Generate a validated Workflow from a natural language goal.

    Returns a Workflow on success, or InsufficientTools if the goal
    cannot be accomplished with available tools.

    Raises WorkflowValidationError if the LLM cannot produce a valid
    workflow after max_retries attempts.
    """
    if settings is None:
        settings = load_settings()

    config = settings.llm
    model = _make_model(config)
    model_settings = _make_model_settings(config)
    system_prompt = build_system_prompt(registry)

    # When thinking is enabled, Anthropic doesn't support tool_choice=required,
    # so we use NativeOutput (JSON schema enforcement at API level).
    # When thinking is disabled, tool output mode (default) works best —
    # it produces more complete structured output.
    output_type: Any
    if config.thinking_budget > 0:
        output_type = NativeOutput(PlanResult)
    else:
        output_type = PlanResult

    agent: Agent[None, PlanResult] = Agent(
        model,
        output_type=output_type,
        instructions=system_prompt,
        model_settings=model_settings,
    )

    user_message = f"Create a workflow to accomplish this goal: {goal}"

    result = await agent.run(user_message)
    plan_result = result.output

    for attempt in range(max_retries + 1):
        if isinstance(plan_result, InsufficientTools):
            return plan_result

        # Convert to Workflow and validate
        workflow = _to_workflow(plan_result)
        try:
            validate(workflow)
            return workflow
        except WorkflowValidationError as e:
            if attempt == max_retries:
                raise

            # Feed validation error back to LLM for retry
            error_message = (
                f"The workflow you generated has validation errors:\n\n{e}\n\n"
                f"Please fix the issues and regenerate the complete workflow."
            )
            result = await agent.run(
                error_message,
                message_history=result.all_messages(),
            )
            plan_result = result.output

    raise WorkflowValidationError("Max retries exceeded")


def _to_workflow(plan_success: PlanSuccess) -> Workflow:
    """Convert LLM output to a Workflow model."""
    return Workflow(
        id=str(uuid.uuid4()),
        name=plan_success.workflow_name,
        steps=[
            Step(
                id=s.id,
                tool_id=s.tool_id,
                name=s.name,
                description=s.description,
                input_mapping=s.input_mapping,
                severity=(
                    StepSeverity.NON_CRITICAL
                    if s.severity == "non_critical"
                    else StepSeverity.CRITICAL
                ),
            )
            for s in plan_success.steps
        ],
        edges=[
            Edge(from_step_id=e.from_step_id, to_step_id=e.to_step_id)
            for e in plan_success.edges
        ],
        status=WorkflowStatus.DRAFT,
    )
