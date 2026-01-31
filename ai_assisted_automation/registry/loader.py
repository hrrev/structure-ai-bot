from pathlib import Path

import yaml

from ai_assisted_automation.models.tool import ToolDefinition


def load_from_yaml(path: str | Path) -> ToolDefinition:
    with open(path) as f:
        data = yaml.safe_load(f)
    return ToolDefinition(**data)
