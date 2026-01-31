from pathlib import Path

from ai_assisted_automation.models.tool import ToolDefinition
from ai_assisted_automation.registry.loader import load_from_yaml


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def load_directory(self, directory: str | Path) -> None:
        directory = Path(directory)
        for yaml_file in directory.glob("*.yaml"):
            tool = load_from_yaml(yaml_file)
            self._tools[tool.id] = tool

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.id] = tool

    def get_tool(self, tool_id: str) -> ToolDefinition:
        if tool_id not in self._tools:
            raise KeyError(f"Tool not found: {tool_id}")
        return self._tools[tool_id]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tools_context(self) -> str:
        lines = []
        for tool in self._tools.values():
            lines.append(f"- {tool.id}: {tool.name} — {tool.description}")
        return "\n".join(lines)

    def get_tool_map(self) -> dict[str, ToolDefinition]:
        return dict(self._tools)
