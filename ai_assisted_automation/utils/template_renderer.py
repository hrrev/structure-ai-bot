"""Template renderer with type-preserving substitution."""

import re
from typing import Any

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def render_template(
    template: Any,
    values: dict[str, Any],
    strict: bool = True,
) -> Any:
    """Recursively render a template, substituting ``{{key}}`` placeholders.

    - Exact match ``"{{key}}"`` → type-preserving replacement.
    - Embedded ``"Hello {{name}}"`` → string interpolation.
    - No placeholder → literal passthrough.
    - *strict* mode raises on missing keys; non-strict keeps placeholder as-is.
    """
    if isinstance(template, dict):
        return {k: render_template(v, values, strict) for k, v in template.items()}
    if isinstance(template, list):
        return [render_template(item, values, strict) for item in template]
    if isinstance(template, str):
        return _render_string(template, values, strict)
    # int, float, bool, None — passthrough
    return template


def _render_string(template: str, values: dict[str, Any], strict: bool) -> Any:
    stripped = template.strip()
    # Exact match: whole string is a single placeholder → type-preserving
    m = re.fullmatch(r"\{\{(\w+)\}\}", stripped)
    if m and stripped == template:
        key = m.group(1)
        if key in values:
            return values[key]
        if strict:
            raise KeyError(f"Missing template key: {key}")
        return template

    # Embedded placeholders → string interpolation
    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in values:
            return str(values[key])
        if strict:
            raise KeyError(f"Missing template key: {key}")
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replacer, template)


def extract_template_keys(template: Any) -> set[str]:
    """Return set of all ``{{key}}`` placeholder names in *template*."""
    keys: set[str] = set()
    _collect_keys(template, keys)
    return keys


def _collect_keys(template: Any, keys: set[str]) -> None:
    if isinstance(template, dict):
        for v in template.values():
            _collect_keys(v, keys)
    elif isinstance(template, list):
        for item in template:
            _collect_keys(item, keys)
    elif isinstance(template, str):
        keys.update(_PLACEHOLDER_RE.findall(template))
