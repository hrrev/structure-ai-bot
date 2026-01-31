"""
Workflow: Where am I and what's the weather?

Graph:
    step_1 (IP Geolocation)
      ├──→ step_2 (Weather from lat/lon)
      └──→ step_3 (Country info from country code)

All three APIs are free, keyless, and return JSON.
Data flows from step_1 outputs into step_2 and step_3 inputs.
"""

import json

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="geo_weather",
        name="Where am I and what's the weather?",
        steps=[
            Step(
                id="step_1",
                tool_id="ip_geolocation",
                input_mapping={},
                description="Get geolocation from IP",
            ),
            Step(
                id="step_2",
                tool_id="open_meteo",
                input_mapping={
                    "latitude": "step_1.lat",
                    "longitude": "step_1.lon",
                    "current": "temperature_2m,wind_speed_10m",
                },
                description="Get weather at detected location",
            ),
            Step(
                id="step_3",
                tool_id="rest_countries",
                input_mapping={
                    "code": "step_1.countryCode",
                },
                description="Get country details from detected country code",
            ),
        ],
        edges=[
            Edge(from_step_id="step_1", to_step_id="step_2"),
            Edge(from_step_id="step_1", to_step_id="step_3"),
        ],
    )


def main():
    # Load tools
    registry = ToolRegistry()
    registry.load_directory("tools")

    print("=== Tools loaded ===")
    print(registry.get_tools_context())
    print()

    # Build and run
    workflow = build_workflow()
    print(f"=== Workflow: {workflow.name} ===")
    print(f"Steps: {[s.id for s in workflow.steps]}")
    print(f"Edges: {[(e.from_step_id, e.to_step_id) for e in workflow.edges]}")
    print()

    run = execute(workflow, {}, registry.get_tool_map())

    print(f"=== Run result: {run.status.value} ===")
    for r in run.step_results:
        print(f"\n--- {r.step_id} [{r.status.value}] ---")
        if r.error:
            print(f"  ERROR: {r.error}")
        else:
            print(json.dumps(r.output_data, indent=2, default=str)[:800])


if __name__ == "__main__":
    main()
