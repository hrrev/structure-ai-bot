import re
from typing import Any

from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.models.workflow import StepValidation


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []


def validate_data(
    data: dict[str, Any],
    validations: list[StepValidation],
    target: str,
) -> ValidationResult:
    """Run validations matching target against data. Returns errors and warnings."""
    result = ValidationResult()
    for v in validations:
        if v.target != target:
            continue
        value = _resolve_field(data, v.field)
        err = _run_check(value, v.field, v.check, v.value)
        if err:
            msg = v.message if v.message else err
            if v.critical:
                result.errors.append(msg)
            else:
                result.warnings.append(msg)
    return result


def _resolve_field(data: dict[str, Any], field: str) -> Any:
    """Traverse dot-path into data dict. Returns None if path doesn't exist."""
    parts = field.split(".")
    try:
        return StateManager._traverse(data, parts, "<validation>")
    except Exception:
        return None


def _run_check(value: Any, field: str, check: str, param: str | None) -> str | None:
    """Run a single check. Returns error message or None if passed."""
    if check == "not_null":
        if value is None:
            return f"'{field}' is null"
        return None

    if check == "not_empty":
        if value is None or value == "" or value == [] or value == {}:
            return f"'{field}' is empty"
        return None

    if check == "min_length":
        if value is None:
            return f"'{field}' is null (expected min_length {param})"
        try:
            if len(value) < int(param or "0"):
                return f"'{field}' length {len(value)} < {param}"
        except TypeError:
            return f"'{field}' has no length (type: {type(value).__name__})"
        return None

    if check == "regex":
        if value is None:
            return f"'{field}' is null (expected to match /{param}/)"
        if not re.search(param or "", str(value)):
            return f"'{field}' does not match /{param}/"
        return None

    if check == "type":
        type_map = {"str": str, "int": int, "float": float, "list": list, "dict": dict, "bool": bool}
        expected = type_map.get(param or "")
        if expected is None:
            return f"Unknown type check: '{param}'"
        if not isinstance(value, expected):
            return f"'{field}' is {type(value).__name__}, expected {param}"
        return None

    return f"Unknown check: '{check}'"
