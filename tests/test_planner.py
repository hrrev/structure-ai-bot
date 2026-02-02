"""Tests for the LLM planner (mocked — no real API calls)."""

import pytest

from ai_assisted_automation.config.settings import LLMConfig, Settings
from ai_assisted_automation.models.tool import (
    AuthConfig,
    AuthType,
    RequestConfig,
    ResponseExtractConfig,
    ToolDefinition,
)
from ai_assisted_automation.models.workflow import Workflow
from ai_assisted_automation.planner.prompt import build_system_prompt
from ai_assisted_automation.planner.result_types import InsufficientTools, PlanSuccess
from ai_assisted_automation.registry.tool_registry import ToolRegistry
from ai_assisted_automation.utils.exceptions import WorkflowValidationError


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_registry() -> ToolRegistry:
    """Create a registry with a couple of test tools."""
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        id="weather_api",
        name="Weather API",
        description="Get current weather for a location",
        base_url="https://api.weather.com",
        method="GET",
        path="/v1/current",
        auth=AuthConfig(type=AuthType.API_KEY, header="X-Api-Key"),
        request=RequestConfig(query_params=["lat", "lon"]),
        response_extract=ResponseExtractConfig(fields={
            "temperature": "current.temp",
            "humidity": "current.humidity",
        }),
    ))
    registry.register(ToolDefinition(
        id="geocode_city",
        name="Geocode City",
        description="Convert city name to lat/lon coordinates",
        base_url="https://api.geocode.com",
        method="GET",
        path="/v1/search",
        request=RequestConfig(query_params=["q"]),
        response_extract=ResponseExtractConfig(fields={
            "latitude": "results.0.lat",
            "longitude": "results.0.lon",
        }),
    ))
    return registry


def _valid_plan() -> PlanSuccess:
    """A plan that should pass validation."""
    return PlanSuccess(
        workflow_name="City Weather",
        steps=[
            {
                "id": "step_1",
                "tool_id": "geocode_city",
                "name": "Geocode",
                "description": "Convert city to coords",
                "input_mapping": {"q": "$input.city_name"},
            },
            {
                "id": "step_2",
                "tool_id": "weather_api",
                "name": "Weather",
                "description": "Get weather at coords",
                "input_mapping": {
                    "lat": "step_1.latitude",
                    "lon": "step_1.longitude",
                },
            },
        ],
        edges=[{"from_step_id": "step_1", "to_step_id": "step_2"}],
        required_user_inputs=["city_name"],
    )


def _invalid_plan_bad_ref() -> PlanSuccess:
    """A plan with an invalid step reference (step_3 doesn't exist)."""
    return PlanSuccess(
        workflow_name="Bad Workflow",
        steps=[
            {
                "id": "step_1",
                "tool_id": "geocode_city",
                "name": "Geocode",
                "description": "Convert city",
                "input_mapping": {"q": "step_3.output"},
            },
        ],
        edges=[],
        required_user_inputs=[],
    )


# ── Mock helper ───────────────────────────────────────────────────────


class _MockResult:
    """Mimics pydantic-ai RunResult."""

    def __init__(self, output):
        self.output = output
        self._messages = [{"role": "assistant", "content": "mock"}]

    def all_messages(self):
        return self._messages


class _MockAgent:
    """Replaces pydantic_ai.Agent for testing."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

    async def run(self, message, *, message_history=None):
        result = _MockResult(self._responses[self.call_count])
        self.call_count += 1
        return result


def _patch_planner(monkeypatch, responses):
    mock = _MockAgent(responses)
    monkeypatch.setattr("ai_assisted_automation.planner.planner.Agent", lambda *a, **kw: mock)
    monkeypatch.setattr("ai_assisted_automation.planner.planner._make_model", lambda c: "mock")
    return mock


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_happy_path(monkeypatch):
    """Valid plan passes validation and returns a Workflow."""
    registry = _make_registry()
    mock = _patch_planner(monkeypatch, [_valid_plan()])

    from ai_assisted_automation.planner.planner import plan

    settings = Settings(llm=LLMConfig(api_key="test-key"))
    result = await plan("Get weather for a city", registry, settings=settings)
    assert isinstance(result, Workflow)
    assert result.name == "City Weather"
    assert len(result.steps) == 2
    assert result.steps[0].tool_id == "geocode_city"
    assert result.steps[1].tool_id == "weather_api"


@pytest.mark.asyncio
async def test_plan_retry_on_validation_error(monkeypatch):
    """Invalid plan triggers retry; second attempt succeeds."""
    registry = _make_registry()
    mock = _patch_planner(monkeypatch, [_invalid_plan_bad_ref(), _valid_plan()])

    from ai_assisted_automation.planner.planner import plan

    settings = Settings(llm=LLMConfig(api_key="test-key"))
    result = await plan("Get weather", registry, settings=settings)
    assert isinstance(result, Workflow)
    assert mock.call_count == 2  # first attempt + one retry


@pytest.mark.asyncio
async def test_plan_max_retries_exceeded(monkeypatch):
    """All retries produce invalid plans -> raises WorkflowValidationError."""
    registry = _make_registry()
    mock = _patch_planner(monkeypatch, [_invalid_plan_bad_ref()] * 5)

    from ai_assisted_automation.planner.planner import plan

    settings = Settings(llm=LLMConfig(api_key="test-key"))
    with pytest.raises(WorkflowValidationError):
        await plan("Impossible goal", registry, max_retries=2, settings=settings)

    # 1 initial + 2 retries = 3 calls
    assert mock.call_count == 3


@pytest.mark.asyncio
async def test_plan_insufficient_tools(monkeypatch):
    """InsufficientTools response is returned directly without validation."""
    registry = _make_registry()
    insufficient = InsufficientTools(
        reason="No email sending tool available",
        missing_capabilities=["SMTP email sender"],
    )
    mock = _patch_planner(monkeypatch, [insufficient])

    from ai_assisted_automation.planner.planner import plan

    settings = Settings(llm=LLMConfig(api_key="test-key"))
    result = await plan("Send an email", registry, settings=settings)
    assert isinstance(result, InsufficientTools)
    assert "email" in result.reason.lower()


def test_build_system_prompt_includes_tools():
    """System prompt contains tool IDs, descriptions, and output fields."""
    registry = _make_registry()
    prompt = build_system_prompt(registry)

    # Tool IDs present
    assert "weather_api" in prompt
    assert "geocode_city" in prompt

    # Descriptions present
    assert "Get current weather" in prompt
    assert "Convert city name" in prompt

    # Output fields present
    assert "temperature" in prompt
    assert "latitude" in prompt
    assert "longitude" in prompt

    # Input params present
    assert "lat" in prompt
    assert "lon" in prompt
    assert "q" in prompt

    # Input mapping syntax explained
    assert "$input." in prompt
    assert "step_N" in prompt or "step_1" in prompt


def test_build_system_prompt_legacy_tool():
    """Legacy tools (with parameters list, no request config) render correctly."""
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        id="old_tool",
        name="Legacy Tool",
        description="A legacy tool with flat parameters",
        base_url="https://api.example.com",
        method="GET",
        path="/v1/data/{id}",
        parameters=["id", "format"],
    ))

    prompt = build_system_prompt(registry)
    assert "old_tool" in prompt
    assert "Legacy Tool" in prompt
    assert "id" in prompt
    assert "format" in prompt
