"""Build the system prompt for the LLM planner from the tool registry."""

from ai_assisted_automation.models.tool import AuthType, ToolDefinition
from ai_assisted_automation.registry.tool_registry import ToolRegistry
from ai_assisted_automation.utils.template_renderer import extract_template_keys


def build_system_prompt(registry: ToolRegistry) -> str:
    """Assemble the full system prompt with tool catalog and rules."""
    tools_section = _render_tool_catalog(registry.list_tools())
    return _SYSTEM_PROMPT_TEMPLATE.format(tools_section=tools_section)


def _render_tool_catalog(tools: list[ToolDefinition]) -> str:
    blocks: list[str] = []
    for tool in sorted(tools, key=lambda t: t.id):
        blocks.append(_render_tool(tool))
    return "\n\n".join(blocks)


def _render_tool(tool: ToolDefinition) -> str:
    lines: list[str] = []
    url = tool.base_url.rstrip("/")
    if tool.path:
        url += "/" + tool.path.lstrip("/")
    lines.append(f"### {tool.id}")
    lines.append(f"**Name:** {tool.name}")
    if tool.description:
        lines.append(f"**Description:** {tool.description}")
    lines.append(f"**Method:** {tool.method.upper()}")
    lines.append(f"**URL:** {url}")

    # Auth
    auth = tool.get_auth_config()
    if auth.type != AuthType.NONE:
        lines.append(f"**Auth:** {auth.type.value} (credentials provided at runtime)")

    # Input parameters
    inputs = _get_input_params(tool)
    if inputs:
        lines.append(f"**Input parameters:** {', '.join(sorted(inputs))}")

    # Available outputs
    outputs = _get_output_fields(tool)
    if outputs:
        lines.append("**Available outputs:**")
        for key, path in sorted(outputs.items()):
            lines.append(f"  - `{key}` (from `{path}`)")
    else:
        lines.append("**Available outputs:** raw JSON response (access fields via dot-path)")

    return "\n".join(lines)


def _get_input_params(tool: ToolDefinition) -> set[str]:
    """Extract all input parameter names a tool accepts."""
    params: set[str] = set()

    # Legacy tools
    if tool.parameters:
        params.update(tool.parameters)

    # New-style tools
    if tool.request:
        params.update(tool.request.path_params)
        params.update(tool.request.query_params)
        if tool.request.body:
            params.update(extract_template_keys(tool.request.body))

    return params


def _get_output_fields(tool: ToolDefinition) -> dict[str, str]:
    """Get the response_extract fields map, or empty if none."""
    if tool.response_extract and tool.response_extract.fields:
        return dict(tool.response_extract.fields)
    return {}


_SYSTEM_PROMPT_TEMPLATE = """\
You are a workflow planner. Given a user's goal, produce an execution graph \
of API call steps using the available tools below.

## Available Tools

{tools_section}

## Step Format

Each step you produce must have:
- **id**: Sequential identifiers: "step_1", "step_2", etc.
- **tool_id**: Must match an available tool ID exactly (case-sensitive).
- **name**: Short human-readable label for DAG visualization.
- **description**: What this step accomplishes.
- **input_mapping**: REQUIRED — this is the most critical field. It must be a non-empty \
dict mapping each tool input parameter to its data source. Every tool parameter listed \
under "Input parameters" MUST have an entry. Values are one of:
  - `"$input.X"` — a value the user provides at runtime (e.g. `"$input.city_name"`).
  - `"step_N.field"` — output from a previous step. Use the output field names listed \
above (e.g. `"step_1.country_name"`). Deep nested access is supported: \
`"step_1.results.0.latitude"`.
  - A plain string with no dots — a literal constant (e.g. `"us-east-1"`, `"snippet"`).
  A step with an empty input_mapping `{{}}` will fail at execution. Always populate it.
- **severity**: `"critical"` (default) or `"non_critical"`. Mark enrichment/optional \
steps as non_critical so workflow continues if they fail.

## Edges

Edges are optional. The system auto-infers edges from input_mapping step references. \
Only provide explicit edges if you need ordering beyond what input_mapping implies.

## Rules

1. Every step must use a tool from the available tools list. Do not invent tool IDs.
2. tool_id must match exactly (case-sensitive).
3. input_mapping keys must match the tool's expected input parameters.
4. Step references must form a DAG — no cycles allowed.
5. If the available tools CANNOT accomplish the user's goal, respond with \
kind="insufficient_tools" and explain what capabilities are missing.
6. Minimize the number of steps. Maximize parallelism — steps with no data \
dependencies between them can run in parallel.
7. List ALL values the user must provide at runtime in required_user_inputs \
(just the names without the "$input." prefix, e.g. ["city_name", "api_key"]).
8. When a tool has response_extract output fields, use those field names in \
downstream step references (e.g. step_1.country_name), not raw API paths.

## Output Format

Respond with a JSON object matching one of these two schemas:

### PlanSuccess (kind="plan")
```json
{{
  "kind": "plan",
  "workflow_name": "Descriptive Workflow Name",
  "steps": [
    {{
      "id": "step_1",
      "tool_id": "tool_id_here",
      "name": "Short Label",
      "description": "What this step does",
      "input_mapping": {{"param": "$input.value"}},
      "severity": "critical"
    }}
  ],
  "edges": [],
  "required_user_inputs": ["value"]
}}
```

### InsufficientTools (kind="insufficient_tools")
```json
{{
  "kind": "insufficient_tools",
  "reason": "Why the goal cannot be accomplished",
  "missing_capabilities": ["what tool or API is needed"]
}}
```
"""
