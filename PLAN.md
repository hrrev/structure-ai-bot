# AI-Assisted Automation — Architecture & Plan

## Project Goal

Build an engine where an LLM planner can take a user's natural language goal (e.g., "Get the weather for the top 3 cities by GitHub contributor count for repo X"), decompose it into a DAG of API calls, and execute the entire workflow automatically. The human approves the plan; the engine handles validation, ordering, data flow, and execution.

The system is designed so that **the graph format is the contract between the LLM and the engine**. The LLM outputs steps + input_mappings + edges; the engine does the rest.

---

## Major Components

### 1. Models (`models/`)

#### `tool.py` — What an API tool can do

A `ToolDefinition` describes a single API endpoint: its URL, HTTP method, auth requirements, request shape, and which response fields matter.

**Design rationale**: Tools are defined in YAML, loaded by Pydantic. The model has two layers:

- **Legacy fields** (`auth_type`, `auth_header`, `parameters`): the original flat design. Supports simple GET/POST with a single auth header. All resolved inputs are sent as query params (GET) or JSON body (POST) — no control over what goes where.
- **New structured fields** (`auth: AuthConfig`, `request: RequestConfig`, `response_extract: ResponseExtractConfig`): added to support nested bodies, path/query/header separation, and cherry-picking response fields.

Both layers coexist. `get_auth_config()` provides a unified accessor that checks new fields first, falls back to legacy. The api_client dispatches to different code paths based on whether `request` is present.

Why not migrate old tools? Because the legacy path is battle-tested and there are existing YAML files. Forcing migration for no functional gain would be unnecessary churn.

**AuthConfig** supports `none`, `api_key`, `bearer`, and `basic`. OAuth2 is deliberately excluded — it requires a multi-step token acquisition flow that should be modeled as a separate workflow step, not baked into auth config.

**RequestConfig** separates concerns that the legacy path conflates:
- `path_params`: substituted into the URL template (`/orgs/{org_id}/orders`), then removed from the input dict so they don't also appear in the body.
- `query_params`: extracted into `?key=value`, also removed from body inputs.
- `headers`: template-rendered custom headers (e.g., idempotency keys). Auth headers are added separately.
- `body`: a nested dict template with `{{placeholder}}` syntax. Supports type preservation — `"{{line_items}}"` where `line_items` is a list stays a list in the JSON body.

**ResponseExtractConfig** defines a `fields` mapping from output key to dot-path into the response JSON. When present, only extracted fields become the step's output. This means downstream steps reference `step_1.order_id` instead of `step_1.data.order.id`. The `strict` flag controls whether missing fields raise errors or return `None`.

Why extract at the tool level? Because the LLM planner needs to know what fields are available for downstream mapping. If extraction is defined in the tool, the planner prompt can include "this tool outputs: order_id, status" — much simpler than "this tool returns a nested JSON, navigate to data.order.id for the order ID."

#### `workflow.py` — The execution graph

A `Workflow` has `steps` (what to do) and `edges` (ordering constraints). Each `Step` has:
- `tool_id`: which tool to call
- `input_mapping`: where each input value comes from (`$input.city`, `step_1.lat`, or a literal)

**Design rationale**: The graph uses explicit string IDs (`step_1`, `step_2`) rather than auto-generated UUIDs because the LLM generates these — human-readable IDs make the graph inspectable and debuggable.

Edges are `from_step_id → to_step_id` pairs. They're now semi-optional: if the LLM forgets to specify an edge but the input_mapping clearly references a prior step, edge inference fills the gap. This makes the format more forgiving for LLM generation.

#### `run.py` — Execution results

Record of a workflow execution. Each step gets a `StepResult` with status (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED`), output data, optional error, and `started_at`/`finished_at` timestamps. `Run` itself also has timestamps and a `user_inputs` dict. The executor pre-populates all step results as PENDING, then updates them in place as steps execute, enabling SSE streaming of live progress.

### 2. Graph Operations (`graph/`)

#### `validator.py` — Correctness checks

Runs three passes in order:
1. **Edge inference** (`infer_edges()`): scan all `input_mapping` values for `step_X.field` patterns, add missing edges. Mutates `workflow.edges` in place so all downstream code sees the complete edge set.
2. **Reference check**: every edge must point to existing step IDs.
3. **Cycle detection**: DFS-based, three-color (white/gray/black). Raises on back-edge.
4. **Input mapping validation**: every `step_X.field` reference must point to a step that is a transitive predecessor (reachable via edges). Catches impossible data flows.

**Design decision — inference before validation**: We chose to infer edges *before* validation rather than after. This means the validator operates on the complete edge set, and input_mapping validation naturally passes for inferred edges. The alternative (validate first, infer later) would require the validator to somehow "know" that missing edges will be added — more complex, more fragile.

**Design decision — mutation**: `validate()` mutates `workflow.edges`. This is intentional: the workflow object should reflect reality after validation. The topological sort that runs next sees the complete edges. If we returned a new edge list instead, every downstream consumer would need to accept it as a parameter.

#### `topological_sort.py` — Execution order

Kahn's algorithm with sorted tie-breaking for determinism. Takes the workflow (with already-inferred edges) and returns a flat list of step IDs in execution order.

No changes were needed here for the new features — it reads `workflow.edges` which are already complete after validation.

#### `edge_inference.py` — Filling gaps

Scans `input_mapping` values with regex `^(?!\$input\.)([a-zA-Z_]\w*)\..*$`:
- Skips `$input.*` references (user inputs, not step dependencies)
- Skips literals (no dot = no step reference)
- Skips self-references (`step_1` referencing `step_1`)
- Extracts the step ID before the first dot
- Adds edge if that step exists and the edge isn't already explicit

Returns merged list: all explicit edges + inferred edges, deduplicated.

### 3. Execution Engine (`executor/`)

#### `workflow_executor.py` — Orchestration

The top-level `execute()` function:
1. Validates the workflow (which infers edges)
2. Topologically sorts steps
3. Iterates in order, calling `step_executor.execute()` for each
4. On first failure, skips all remaining steps

Currently **sequential only**. The topo sort often produces independent steps that could run in parallel (e.g., step_2, step_3, step_4 in a fan-out), but the executor doesn't exploit this yet.

#### `step_executor.py` — Single step

Resolves input_mapping via StateManager, calls api_client, stores output. Catches all exceptions and wraps them in a `StepResult` with `FAILED` status. This is the error boundary — individual step failures don't crash the run.

#### `api_client.py` — HTTP dispatch

Two code paths, selected by `tool.request is not None`:

**Legacy path** (`_call_legacy`): Original behavior. GET sends all resolved inputs as query params. POST sends all as JSON body. URL template substitution pops matching params. List responses get wrapped in `{"items": [...], "count": N}`.

**New config path** (`_call_with_config`): Explicit routing:
1. Path params substituted into URL, popped from inputs
2. Query params extracted, popped from inputs
3. Auth headers built from `AuthConfig` (supports bearer, api_key, basic)
4. Custom headers rendered from template
5. Body rendered from template (type-preserving)
6. HTTP request executed via `requests.request()` (supports all methods)
7. If `response_extract` defined: cherry-pick fields using `StateManager._traverse`
8. If not: full response returned (with legacy list wrapping)

**Design decision — two paths, not migration**: We explicitly chose NOT to rewrite the legacy path or make it go through the new config path with default settings. Reasons:
- The legacy path has existing tests and known-working behavior
- Making it go through RequestConfig would change subtle behaviors (e.g., how inputs are split between query and body)
- New tools opt into the new path by having a `request` key in YAML; old tools don't need changes

**Design decision — `_traverse` reuse**: Response extraction reuses `StateManager._traverse()` as a static method rather than duplicating the dot-path traversal logic. This ensures consistent behavior between "navigate step output" and "navigate API response."

#### `state_manager.py` — Data flow resolution

Resolves `input_mapping` values at runtime:
- `$input.field` → looks up user inputs
- `step_X.field.nested.0.path` → looks up step output, traverses with `_traverse`
- `literal` (no dots, no `$input.`) → returns as-is

`_traverse` handles both dict key access and list index access (numeric segments parsed as `int`). Raises `StateResolutionError` with context on any navigation failure.

### 4. Template Renderer (`utils/template_renderer.py`)

Recursive function that walks any Python value (dict, list, str, primitive):

- **Dict**: recurse into each value
- **List**: recurse into each element
- **String, exact match** (`"{{key}}"` and nothing else): type-preserving replacement. If the value is an int, you get an int back. If it's a list, you get a list. This is critical for JSON body construction where `"{{line_items}}"` must produce `[{...}, {...}]`, not `"[{...}, {...}]"`.
- **String, embedded** (`"Hello {{name}}"`): all placeholders stringified and interpolated
- **Primitive** (int, float, bool, None): passthrough

Strict mode raises `KeyError` on missing keys. Non-strict keeps the `{{placeholder}}` text as-is (used for headers where a missing optional header value shouldn't crash the request).

### 5. Tool Registry (`registry/`)

Simple in-memory dict. `load_directory()` globs for `*.yaml` files, parses each with Pydantic. No validation beyond what Pydantic does — unknown fields are ignored (Pydantic v2 default), missing required fields raise.

The loader doesn't need changes for new tool features because Pydantic handles optional fields automatically. A YAML with no `auth`/`request`/`response_extract` keys produces a `ToolDefinition` with those fields as `None`.

---

## Decisions Made and Their Rationale

| Decision | Why |
|----------|-----|
| Edge inference before validation, not after | Validator sees complete graph; no special-casing needed |
| Mutation of `workflow.edges` in place | Simplest contract for downstream code (topo sort, executor) |
| Two-path API client dispatch | Zero risk to existing tools; clean separation of concerns |
| Type-preserving template rendering | JSON bodies need real types, not everything-as-string |
| Response extraction at tool level | LLM planner needs to know available output fields at planning time |
| No GraphQL special-casing | POST with structured body template handles it naturally |
| OAuth2 deferred | It's a multi-step flow that should be a workflow step, not auth config |
| Sequential execution only (for now) | Correct-first; parallelism is an optimization, not a correctness requirement |
| `StateManager._traverse` reused for response extraction | One implementation of dot-path traversal, consistent behavior |
| Legacy fields kept alongside new models | Backward compat; no forced migration of existing YAML tools |

---

## What's Left for Future Sprints

### Near-Term (Next Sprint Candidates)

#### 1. LLM Planner (`planner/`)
The core value proposition. Given:
- Tool registry (what's available, what each tool returns)
- User's goal in natural language
- Available `$input.*` values

Generate a `Workflow` (steps, input_mappings, edges). The format is already LLM-friendly:
- Flat step list with simple string IDs
- `input_mapping` is explicit about data sources
- Edge auto-inference reduces errors (LLM doesn't need to manually track edges)
- `response_extract.fields` tells the LLM exactly what fields are available downstream

The planner prompt should include tool definitions with their `response_extract.fields` so the LLM knows what outputs are available for downstream mapping.

#### 2. Parallel Step Execution
The topo sort produces a flat list, but steps at the same "level" (same in-degree reduction round) could run concurrently. Implementation options:
- `asyncio.gather()` for I/O-bound API calls
- `concurrent.futures.ThreadPoolExecutor` for simplicity
- The topo sort could return levels (list of lists) instead of a flat list

Requires making `StateManager` thread-safe (or using per-step snapshots).

#### 3. Step-Level Input/Output Validation
Steps can succeed with null/empty outputs that silently propagate downstream. Add a `validations` list to `Step` with rules like `not_null`, `not_empty`, `regex`, `type` checks on input or output fields. Validation runs in `step_executor` — output checks after API call, input checks before. Failures mark the step as FAILED with descriptive error messages.

### Medium-Term

#### 5. Pre/Post Hook Middleware
A tool type hierarchy for shared behavior:

```
Tool (base)
  └── APITool (adds HTTP semantics)
        ├── pre_hooks: [auth_injection, rate_limiting, correlation_id]
        ├── post_hooks: [response_logging, retry_on_429, error_transform]
        └── concrete tools
```

Hooks registered at interface level (all API tools), tool level (specific tool), or workflow level (all steps in a run). Implementation: middleware chain in step_executor, sitting between input resolution and api_client.call().

Use cases:
- Auth pre-hook at APITool level → every API tool gets correct auth without per-tool config
- Logging post-hook → every API call logged automatically
- Rate limiting pre-hook → shared across tools hitting the same provider
- Response transform post-hook → normalize error formats across different APIs

#### 6. Exploration-Based Graph Planning
Instead of generating a graph purely from tool docs, the planner makes live API calls during planning:

1. LLM picks candidate tools from registry
2. LLM makes exploratory calls with sample/test data
3. LLM sees real response JSON — knows exact field names and nesting
4. LLM builds graph with correct `input_mapping` references
5. User approves → graph saved for repeated execution

This is "plan-by-doing" — the first run is exploratory, subsequent runs use the fixed graph. Requires real credentials during planning. Complements doc-based planning; both modes should be supported.

#### 7. Retry and Error Handling
Currently: one failure → skip all remaining steps. Future:
- Per-step retry policy (max attempts, backoff)
- Conditional continuation (fail-open for non-critical steps)
- Error transformation (normalize different API error formats)
- Timeout per step (currently hardcoded 30s)

#### 8. OAuth2 Auth Type
Model it as a pre-hook or a dedicated "token acquisition" step that runs before the workflow, storing the token in state for subsequent steps to reference.

### Long-Term

#### 9. Workflow Composition
Workflows that call other workflows as steps. Enables reusable sub-workflows (e.g., "authenticate with provider X" as a sub-workflow used by multiple parent workflows).

#### 10. Streaming and Webhooks
For long-running workflows: stream step results as they complete rather than waiting for the full run. WebSocket or SSE endpoint.

#### 11. Multi-Provider Credential Management
Centralized secret store integration (Vault, AWS Secrets Manager) instead of passing `tool_configs` dicts manually.

---

## Test Coverage Summary

| Module | Tests | File |
|--------|-------|------|
| Template renderer | 17 | `tests/test_template_renderer.py` |
| API client (new path) | 13 | `tests/test_api_client_extended.py` |
| API client (form-encoded) | — | `tests/test_api_client_form_encoded.py` |
| API client (legacy) | 7 | `tests/test_api_client.py` |
| State manager | 8 | `tests/test_state_manager.py` |
| Graph validator | 7 | `tests/test_graph_validator.py` |
| Edge inference | 6 | `tests/test_edge_inference.py` |
| Topological sort | 4 | `tests/test_topological_sort.py` |
| Workflow executor | 3 | `tests/test_workflow_executor.py` |
| Workflow executor tracking | — | `tests/test_workflow_executor_tracking.py` |
| Step executor | 2 | `tests/test_step_executor.py` |
| REST API | — | `tests/test_api.py` |
| JSON storage | — | `tests/test_storage.py` |
| **Total** | **88** | |

All tests pass. Run with `pytest tests/ -v`.

---

## Tool YAML Format Reference

### Legacy (still supported)

```yaml
id: ip_geolocation
name: IP Geolocation
base_url: http://ip-api.com
method: GET
path: /json
auth_type: none
parameters: [fields]
```

### New (full-featured)

```yaml
id: create_order
name: Create Order
base_url: https://api.example.com
method: POST
path: /v2/orders/{org_id}

auth:
  type: bearer

request:
  path_params: [org_id]
  query_params: [dry_run]
  headers:
    X-Idempotency-Key: "{{idempotency_key}}"
  body:
    customer:
      email: "{{email}}"
      tier: "{{tier}}"
    items: "{{line_items}}"
    metadata:
      source: "automation"

response_extract:
  fields:
    order_id: data.order.id
    status: data.order.status
  strict: true
```

### GraphQL (just a structured POST)

```yaml
id: github_graphql
name: GitHub GraphQL
base_url: https://api.github.com/graphql
method: POST

auth:
  type: bearer

request:
  body:
    query: |
      query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          stargazerCount
        }
      }
    variables:
      owner: "{{owner}}"
      name: "{{repo}}"

response_extract:
  fields:
    stars: data.repository.stargazerCount
```
