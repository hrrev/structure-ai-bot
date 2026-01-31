import re
from typing import Any

import requests

from ai_assisted_automation.models.tool import AuthType, ToolDefinition
from ai_assisted_automation.utils.exceptions import StepExecutionError


def call(
    tool: ToolDefinition,
    resolved_inputs: dict[str, Any],
    tool_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    tool_config = tool_config or {}
    url = _build_url(tool, resolved_inputs)
    headers = _build_auth_headers(tool, tool_config)

    try:
        if tool.method.upper() == "GET":
            resp = requests.get(url, params=resolved_inputs, headers=headers, timeout=30)
        else:
            resp = requests.post(url, json=resolved_inputs, headers=headers, timeout=30)
    except requests.RequestException as e:
        raise StepExecutionError(f"HTTP request failed: {e}")

    if resp.status_code >= 400:
        raise StepExecutionError(
            f"HTTP {resp.status_code}: {resp.text}"
        )

    try:
        data = resp.json()
        if isinstance(data, list):
            return {"items": data, "count": len(data)}
        return data
    except ValueError:
        return {"status_code": resp.status_code, "body": resp.text}


def _build_url(tool: ToolDefinition, resolved_inputs: dict[str, Any]) -> str:
    path = tool.path
    # Replace {param} placeholders in path
    for match in re.findall(r"\{(\w+)\}", path):
        if match in resolved_inputs:
            path = path.replace(f"{{{match}}}", str(resolved_inputs.pop(match)))
    return tool.base_url.rstrip("/") + "/" + path.lstrip("/") if path else tool.base_url


def _build_auth_headers(
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
