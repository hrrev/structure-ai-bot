"""
Workflow: Travel Destination Briefing

Graph:
    $input.city                          $input.home_currency
        │                                        │
     step_1 (geocode city)                   step_4 (exchange rates)
      ╱        ╲                                 │
  step_2     step_3                              │
 (weather)  (country info)                       │
      ╲        ╱             ╱
            step_5 (POST briefing to httpbin)

5 steps. step_1 fans out to step_2 + step_3.
step_4 runs independently from $input.
step_5 merges all four predecessors.
"""

import json

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="travel_briefing",
        name="Travel Destination Briefing",
        steps=[
            Step(
                id="step_1",
                tool_id="geocode_city",
                input_mapping={
                    "name": "$input.city",
                    "count": "1",
                },
                description="Geocode the destination city",
            ),
            Step(
                id="step_2",
                tool_id="open_meteo",
                input_mapping={
                    "latitude": "step_1.results.0.latitude",
                    "longitude": "step_1.results.0.longitude",
                    "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
                },
                description="Get weather at destination",
            ),
            Step(
                id="step_3",
                tool_id="rest_countries",
                input_mapping={
                    "code": "step_1.results.0.country_code",
                },
                description="Get country info for destination",
            ),
            Step(
                id="step_4",
                tool_id="exchange_rate",
                input_mapping={
                    "base": "$input.home_currency",
                },
                description="Get exchange rates for home currency",
            ),
            Step(
                id="step_5",
                tool_id="httpbin_post",
                input_mapping={
                    "city": "step_1.results.0.name",
                    "country": "step_1.results.0.country",
                    "temperature_c": "step_2.current.temperature_2m",
                    "wind_kmh": "step_2.current.wind_speed_10m",
                    "humidity_pct": "step_2.current.relative_humidity_2m",
                    "country_population": "step_3.items.0.population",
                    "country_region": "step_3.items.0.region",
                    "exchange_base": "step_4.base_code",
                    "exchange_rates_count": "step_4.time_last_update_utc",
                },
                description="POST travel briefing to webhook",
            ),
        ],
        edges=[
            Edge(from_step_id="step_1", to_step_id="step_2"),
            Edge(from_step_id="step_1", to_step_id="step_3"),
            Edge(from_step_id="step_2", to_step_id="step_5"),
            Edge(from_step_id="step_3", to_step_id="step_5"),
            Edge(from_step_id="step_4", to_step_id="step_5"),
        ],
    )


def main():
    registry = ToolRegistry()
    registry.load_directory("tools")

    workflow = build_workflow()
    city = input("Destination city (e.g. 'Tokyo'): ").strip() or "Tokyo"
    currency = input("Home currency   (e.g. 'USD'):   ").strip() or "USD"

    print(f"\n=== Running: {workflow.name} ===")
    print(f"    City: {city}, Home currency: {currency}\n")

    run = execute(
        workflow,
        {"city": city, "home_currency": currency},
        registry.get_tool_map(),
    )

    print(f"=== Run result: {run.status.value} ===")
    for r in run.step_results:
        print(f"\n--- {r.step_id} [{r.status.value}] ---")
        if r.error:
            print(f"  ERROR: {r.error}")
        else:
            print(json.dumps(r.output_data, indent=2, default=str)[:600])


if __name__ == "__main__":
    main()
