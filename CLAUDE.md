# AI-Assisted Automation — Project Context

## Project Vision

User describes a goal in natural language → LLM decomposes it into a DAG of API call steps → User sees a simplified graph view and approves → System executes the graph → Run history tracked. The graph is saved as a reusable workflow: first run is validated, subsequent runs execute the same fixed graph automatically. Failures are reported, not auto-healed.

This is a **backend-first** Python project. Frontend will come later.

## Two Distinct Phases of Operation

1. **Design Phase** (one-time, with user approval):
   User describes goal → LLM produces execution graph using tool registry context → User reviews simplified view and approves → Validation run executes → If green, workflow saved as reusable

2. **Execution Phase** (repeatable, no user involvement):
   Saved workflow runs on trigger → Each step executes → Results/errors tracked per run → User views run history, gets notified on failures

## Core Concept: The Graph is the Contract

The graph format is the interface between the LLM planner and the execution engine. The LLM outputs steps + input_mappings + edges; the engine handles everything else (validation, ordering, state flow, HTTP calls). This separation is deliberate — the **executor is NOT an LLM**. The graph is fully specified after planning; there's no ambiguity left to resolve at runtime. Using an LLM in the executor would add latency, cost, and nondeterminism for no benefit.

## Phased Build Approach

- **Phase 1** (current): Action nodes only (API calls). Executor is fully deterministic. No decision/transform nodes, no MCP.
- **Phase 2** (future): Decision nodes (scoped LLM calls at runtime) + transform nodes. A decision node has a `decision_prompt`, receives dependency outputs, returns a structured choice. Scoped per-decision LLM calls preferred over a single persistent LLM with full context — cheaper, faster, and most context is irrelevant to the specific decision.
- **Phase 3** (future): MCP server tool calls as another action node type.

## Repository Layout

```
ai_assisted_automation/          # importable package (NOT scripts)
  models/
    tool.py                      # ToolDefinition + AuthConfig, RequestConfig, ResponseExtractConfig
    workflow.py                  # Workflow, Step, Edge, WorkflowStatus
    run.py                       # Run, StepResult, RunStatus
  graph/
    validator.py                 # validate(): edge inference → ref check → cycle check → mapping check
    topological_sort.py          # Kahn's algorithm, deterministic (sorted ties)
    edge_inference.py            # infer_edges(): scan input_mappings, merge with explicit edges
  executor/
    workflow_executor.py         # top-level execute(): validate → topo sort → step loop
    step_executor.py             # execute(): resolve inputs → api_client.call → store output
    api_client.py                # two-path dispatch: _call_with_config() vs _call_legacy()
    state_manager.py             # resolve $input.* and step_X.field.path references
  registry/
    tool_registry.py             # in-memory registry, loads from YAML directory
    loader.py                    # load_from_yaml() — Pydantic parses, no custom logic
  utils/
    template_renderer.py         # render_template(): recursive, type-preserving {{key}} substitution
    exceptions.py                # WorkflowValidationError, StateResolutionError, StepExecutionError
  config/                        # placeholder — no config logic yet
  planner/                       # placeholder — LLM planner not yet implemented
  api/                           # placeholder — no REST API yet
  storage/                       # placeholder — no persistence yet
examples/                        # runnable scripts (outside package, standard Python convention)
  geo_weather_workflow.py        # 3-step: IP geolocation → weather + country info
  github_intel_workflow.py       # 6-step: repo info → 4 parallel fetches → POST summary
  travel_briefing_workflow.py    # 5-step: geocode → weather + country + exchange → POST briefing
tests/                           # 67 tests total
  test_api_client.py             # 7 tests — legacy path
  test_api_client_extended.py    # 13 tests — new config path + backward compat
  test_edge_inference.py         # 6 tests
  test_template_renderer.py      # 17 tests
  test_graph_validator.py        # 7 tests
  test_topological_sort.py       # 4 tests
  test_state_manager.py          # 8 tests
  test_step_executor.py          # 2 tests
  test_workflow_executor.py      # 3 tests
tools/                           # tool YAML definitions (13 tools)
```

## How to Run

```bash
pip install -e ".[dev]"
pytest tests/ -v
python examples/geo_weather_workflow.py
```

## Key Conventions

- **Python 3.12+**, type hints everywhere, `str | None` union syntax.
- **Pydantic v2** for all models — validation is automatic on construction.
- **No classes where functions suffice**: `validator.validate()`, `topological_sort.sort()`, `api_client.call()` are all module-level functions.
- **State is threaded, not global**: `StateManager` is instantiated per run.
- **Tool configs are separate from tool definitions**: secrets live in `tool_configs` dict, never in YAML.
- **TDD workflow**: tests are written alongside implementation, always green before moving on.
- **Backward compatibility is mandatory**: old tool YAMLs (flat `auth_type`/`auth_header`, no `request`/`response_extract`) still work via the legacy code path. No forced migration.

## Input Mapping Reference Syntax

Three sources for step inputs (established in Session 1 design discussion):

| Prefix | Meaning | Example |
|--------|---------|---------|
| `$input.X` | User-provided runtime value | `"$input.email"` |
| `step_N.X` | Output from a previous step | `"step_1.account_id"` |
| plain value (no dots) | Literal constant | `"us-east-1"` |

Deep nested access is supported: `step_1.results.0.latitude` traverses into nested dicts and arrays (numeric segments parsed as list indices).

## Template Syntax (in RequestConfig body/headers)

- `"{{key}}"` (exact match) — type-preserving: int stays int, list stays list
- `"Hello {{name}}"` (embedded) — string interpolation, all values stringified
- `"literal"` (no placeholders) — passed through unchanged

## Decisions Made Across Sessions

### Session 1: Initial Architecture

User requirements established:
- **Single-shot planning** (no iterative replanning). Workflows are recurring; first run validates, then saved.
- **Graph = plain JSON/dict** (not NetworkX or formal graph library). Simple and serializable.
- **LLM planner has full tool registry context**. At current scale no retrieval needed.
- **No replanning at runtime**. Graph is fixed after validation. Failures are reported, not auto-healed.
- **User approves the initial graph only**. Execution details are hidden from them.
- **Executor is deterministic** for Phase 1. The LLM is only involved in planning, not execution.

### Session 2: Implementation & Real-World Testing

- Built core engine (models, graph ops, executor) with 28 tests.
- Tested with real free APIs (ip-api.com, open-meteo.com, restcountries.com).
- Discovered and fixed: API list responses need wrapping (`{"items": [...], "count": N}`), auth headers should be skipped when token is empty, nested field access needed for real API responses (`step_1.results.0.latitude`).
- Built two complex example workflows: GitHub Intel (6-step fan-out/fan-in) and Travel Briefing (5-step mixed dependencies).

### Session 3: Complex API Support Design

Identified gaps for real-world APIs:
- Flat request bodies can't handle nested JSON (e.g., Stripe charges with nested customer objects)
- No way to send query params + body simultaneously
- No custom headers beyond auth
- No response field extraction (downstream steps reference deep nested paths)
- No GraphQL support

Design decisions:
1. **Two-path API client** — new config path for tools with `request` key; legacy path untouched. Zero risk to existing tools.
2. **Edge auto-inference** — LLM is expected to provide edges but if it misses one, `infer_edges()` fills the gap from input_mapping analysis. Explicit edges always respected; inference only fills gaps.
3. **GraphQL needs no special handling** — it's just a POST with `{"query": "...", "variables": {...}}` body template.
4. **Response extraction at tool level** — `response_extract.fields` maps output keys to dot-paths. Makes downstream references cleaner (`step_1.order_id` vs `step_1.data.order.id`) and tells the LLM planner exactly what outputs are available.
5. **OAuth2 deliberately deferred** — it's a multi-step token flow that should be a separate workflow step, not baked into auth config.
6. **Type-preserving template rendering** — `"{{line_items}}"` where value is a list produces a real JSON array, not a stringified one. Critical for nested API bodies.
7. **Edge inference before validation** — validator mutates `workflow.edges` in place so all downstream code (topo sort, executor) sees the complete edge set.

### Session 3: Future Architecture Ideas Discussed

- **Pre/post hooks at tool interface level**: `Tool → APITool → SpecificTool` hierarchy where APITool automatically gets auth injection, retry, logging hooks. Hooks can be registered at interface level, tool level, or workflow level. Implementation would be a middleware chain in step_executor. Deferred to dedicated sprint.
- **Exploration-based graph planning**: LLM makes live API calls during planning to discover actual response shapes, then builds graph with correct field references. "Plan-by-doing" where first run is exploratory. Requires real credentials during planning.
- **LLM-friendly graph format**: Format is already good for LLM generation — flat step list, explicit input_mapping, edge auto-inference reduces errors, response_extract.fields tells the LLM what's available downstream.
- **Tool creation from API docs**: The YAML format is explicit enough that an LLM can generate a tool definition directly from API documentation.

## What's Not Built Yet

- `planner/` — LLM-based workflow generation from natural language (the core value prop, Phase 2)
- `api/` — REST API to expose the engine (FastAPI, natural fit with Pydantic models)
- `storage/` — workflow and run persistence (JSON files for dev, DB for prod)
- `config/` — runtime configuration (timeouts, retries, provider settings)
- Pre/post hook middleware chain (discussed, deferred)
- Exploration-based graph planning (discussed, deferred)
- Decision + transform node types (Phase 2 — scoped LLM calls at decision points)
- MCP tool call support (Phase 3)
- OAuth2 auth type
- Parallel step execution (currently sequential even when topo order allows parallelism)
- Multipart file uploads
- Pagination / loop constructs
- Retry policies per step

## Git Author

Himanshu Rajoria <himanshurajoriaiitkgp@gmail.com>
