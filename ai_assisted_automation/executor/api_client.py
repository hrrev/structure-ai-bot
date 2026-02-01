import base64
import re
from typing import Any

import requests

from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.models.tool import AuthType, ToolDefinition
from ai_assisted_automation.utils.exceptions import StepExecutionError
from ai_assisted_automation.utils.template_renderer import render_template


def call(
    tool: ToolDefinition,
    resolved_inputs: dict[str, Any],
    tool_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    tool_config = tool_config or {}
    if tool.request is not None:
        return _call_with_config(tool, resolved_inputs, tool_config)
    return _call_legacy(tool, resolved_inputs, tool_config)


# ── New config-driven path ──────────────────────────────────────────


def _call_with_config(
    tool: ToolDefinition,
    resolved_inputs: dict[str, Any],
    tool_config: dict[str, str],
) -> dict[str, Any]:
    inputs = dict(resolved_inputs)
    req = tool.request  # guaranteed not None by caller

    # 1. Path params → substitute in URL, pop from inputs
    path = tool.path
    for param in req.path_params:
        if param in inputs:
            path = path.replace(f"{{{param}}}", str(inputs.pop(param)))

    url = tool.base_url.rstrip("/") + "/" + path.lstrip("/") if path else tool.base_url

    # 2. Query params → extract, pop from inputs
    query: dict[str, Any] = {}
    for param in req.query_params:
        if param in inputs:
            query[param] = inputs.pop(param)

    # 3. Headers → auth + custom rendered headers
    headers = _build_auth_headers_new(tool, tool_config)
    if req.headers:
        rendered_headers = render_template(req.headers, inputs, strict=False)
        headers.update(rendered_headers)

    # 4. Body → render template with remaining inputs
    body: Any = None
    if req.body is not None:
        body = render_template(req.body, inputs, strict=False)

    # 5. Execute HTTP
    method = tool.method.upper()
    try:
        resp = _do_request(method, url, headers, query, body, req.content_type)
    except requests.RequestException as e:
        raise StepExecutionError(f"HTTP request failed: {e}")

    if resp.status_code >= 400:
        raise StepExecutionError(f"HTTP {resp.status_code}: {resp.text}")

    try:
        data = resp.json()
    except ValueError:
        return {"status_code": resp.status_code, "body": resp.text}

    # 6. Response extraction
    if tool.response_extract and tool.response_extract.fields:
        return _extract_response(data, tool.response_extract.fields, tool.response_extract.strict)

    # 7. No extract → legacy list wrapping
    if isinstance(data, list):
        return {"items": data, "count": len(data)}
    return data


def _do_request(
    method: str,
    url: str,
    headers: dict[str, str],
    query: dict[str, Any],
    body: Any,
    content_type: str = "application/json",
) -> requests.Response:
    kwargs: dict[str, Any] = {"headers": headers, "timeout": 30}
    if query:
        kwargs["params"] = query
    if body is not None:
        if content_type == "application/x-www-form-urlencoded":
            kwargs["data"] = body
        else:
            kwargs["json"] = body
    return requests.request(method, url, **kwargs)


def _extract_response(
    data: Any,
    fields: dict[str, str],
    strict: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for output_key, dot_path in fields.items():
        parts = dot_path.split(".")
        try:
            result[output_key] = StateManager._traverse(data, parts, "<response>")
        except Exception:
            if strict:
                raise StepExecutionError(
                    f"Response extraction failed: field '{dot_path}' not found"
                )
            result[output_key] = None
    return result


def _build_auth_headers_new(
    tool: ToolDefinition, tool_config: dict[str, str]
) -> dict[str, str]:
    auth = tool.get_auth_config()
    if auth.type == AuthType.NONE:
        return {}

    token = tool_config.get("auth_token", "")

    if auth.type == AuthType.API_KEY:
        if not token:
            return {}
        header_name = auth.header or "X-API-Key"
        return {header_name: token}

    if auth.type == AuthType.BEARER:
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    if auth.type == AuthType.BASIC:
        username_key = auth.username_key or "auth_username"
        username = tool_config.get(username_key, "")
        password = tool_config.get("auth_token", "")
        if username or password:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {}

    return {}


# ── Legacy path (unchanged) ─────────────────────────────────────────


def _call_legacy(
    tool: ToolDefinition,
    resolved_inputs: dict[str, Any],
    tool_config: dict[str, str],
) -> dict[str, Any]:
    url = _build_url_legacy(tool, resolved_inputs)
    headers = _build_auth_headers_legacy(tool, tool_config)

    try:
        if tool.method.upper() == "GET":
            resp = requests.get(url, params=resolved_inputs, headers=headers, timeout=30)
        else:
            resp = requests.post(url, json=resolved_inputs, headers=headers, timeout=30)
    except requests.RequestException as e:
        raise StepExecutionError(f"HTTP request failed: {e}")

    if resp.status_code >= 400:
        raise StepExecutionError(f"HTTP {resp.status_code}: {resp.text}")

    try:
        data = resp.json()
        if isinstance(data, list):
            return {"items": data, "count": len(data)}
        return data
    except ValueError:
        return {"status_code": resp.status_code, "body": resp.text}


def _build_url_legacy(tool: ToolDefinition, resolved_inputs: dict[str, Any]) -> str:
    path = tool.path
    for match in re.findall(r"\{(\w+)\}", path):
        if match in resolved_inputs:
            path = path.replace(f"{{{match}}}", str(resolved_inputs.pop(match)))
    return tool.base_url.rstrip("/") + "/" + path.lstrip("/") if path else tool.base_url


def _build_auth_headers_legacy(
    tool: ToolDefinition, tool_config: dict[str, str]
) -> dict[str, str]:
    if tool.auth_type == AuthType.NONE:
        return {}
    token = tool_config.get("auth_token", "")
    if not token:
        return {}
    if tool.auth_type == AuthType.API_KEY:
        return {tool.auth_header or "X-API-Key": token}
    if tool.auth_type == AuthType.BEARER:
        return {"Authorization": f"Bearer {token}"}
    return {}
