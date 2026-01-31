from typing import Any

from ai_assisted_automation.utils.exceptions import StateResolutionError


class StateManager:
    def __init__(self) -> None:
        self._user_inputs: dict[str, Any] = {}
        self._step_outputs: dict[str, dict[str, Any]] = {}

    def set_user_inputs(self, inputs: dict[str, Any]) -> None:
        self._user_inputs = inputs

    def store_step_output(self, step_id: str, output_data: dict[str, Any]) -> None:
        self._step_outputs[step_id] = output_data

    def resolve_input_mapping(self, input_mapping: dict[str, str]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in input_mapping.items():
            resolved[key] = self._resolve_value(value)
        return resolved

    def _resolve_value(self, value: str) -> Any:
        if value.startswith("$input."):
            input_key = value[len("$input."):]
            if input_key not in self._user_inputs:
                raise StateResolutionError(f"Missing user input: {input_key}")
            return self._user_inputs[input_key]

        if "." in value:
            parts = value.split(".")
            step_id = parts[0]
            path = parts[1:]
            if step_id not in self._step_outputs:
                raise StateResolutionError(f"Missing output from step: {step_id}")
            return self._traverse(self._step_outputs[step_id], path, step_id)

        return value

    @staticmethod
    def _traverse(data: Any, path: list[str], step_id: str) -> Any:
        current = data
        for segment in path:
            if isinstance(current, list):
                try:
                    current = current[int(segment)]
                except (ValueError, IndexError):
                    raise StateResolutionError(
                        f"Step {step_id}: cannot index list with '{segment}'"
                    )
            elif isinstance(current, dict):
                if segment not in current:
                    raise StateResolutionError(
                        f"Step {step_id} output missing field: {segment}"
                    )
                current = current[segment]
            else:
                raise StateResolutionError(
                    f"Step {step_id}: cannot traverse into {type(current).__name__}"
                )
        return current
