import pytest

from ai_assisted_automation.utils.template_renderer import (
    extract_template_keys,
    render_template,
)


class TestRenderTemplate:
    def test_exact_match_preserves_int(self):
        assert render_template("{{age}}", {"age": 42}) == 42

    def test_exact_match_preserves_list(self):
        items = [1, 2, 3]
        assert render_template("{{items}}", {"items": items}) == [1, 2, 3]

    def test_exact_match_preserves_bool(self):
        assert render_template("{{flag}}", {"flag": True}) is True

    def test_exact_match_preserves_none(self):
        assert render_template("{{val}}", {"val": None}) is None

    def test_embedded_string_interpolation(self):
        result = render_template("Hello {{name}}, you are {{age}}", {"name": "Alice", "age": 30})
        assert result == "Hello Alice, you are 30"

    def test_literal_passthrough(self):
        assert render_template("no placeholders", {}) == "no placeholders"

    def test_nested_dict(self):
        template = {
            "customer": {"email": "{{email}}", "tier": "{{tier}}"},
            "metadata": {"source": "automation"},
        }
        result = render_template(template, {"email": "a@b.com", "tier": "gold"})
        assert result == {
            "customer": {"email": "a@b.com", "tier": "gold"},
            "metadata": {"source": "automation"},
        }

    def test_list_template(self):
        template = ["{{a}}", "literal", "{{b}}"]
        assert render_template(template, {"a": 1, "b": 2}) == [1, "literal", 2]

    def test_primitive_passthrough(self):
        assert render_template(42, {}) == 42
        assert render_template(True, {}) is True

    def test_strict_raises_on_missing(self):
        with pytest.raises(KeyError, match="Missing template key: name"):
            render_template("{{name}}", {}, strict=True)

    def test_non_strict_keeps_placeholder(self):
        assert render_template("{{name}}", {}, strict=False) == "{{name}}"

    def test_non_strict_embedded_keeps_placeholder(self):
        result = render_template("Hello {{name}}", {}, strict=False)
        assert result == "Hello {{name}}"

    def test_type_preserving_list_in_body(self):
        template = {"items": "{{line_items}}", "count": "{{n}}"}
        result = render_template(template, {"line_items": [{"sku": "A"}], "n": 1})
        assert result == {"items": [{"sku": "A"}], "count": 1}


class TestExtractTemplateKeys:
    def test_flat(self):
        assert extract_template_keys("{{a}} and {{b}}") == {"a", "b"}

    def test_nested(self):
        template = {"x": "{{a}}", "y": {"z": "{{b}}"}}
        assert extract_template_keys(template) == {"a", "b"}

    def test_no_keys(self):
        assert extract_template_keys("literal") == set()

    def test_list(self):
        assert extract_template_keys(["{{a}}", "{{b}}"]) == {"a", "b"}
