from ai_assisted_automation.executor.step_validator import validate_data
from ai_assisted_automation.models.workflow import StepValidation


def _v(field, check, target="output", value=None, message="", critical=True):
    return StepValidation(field=field, check=check, target=target, value=value, message=message, critical=critical)


# --- not_null ---

def test_not_null_passes():
    result = validate_data({"name": "Adele"}, [_v("name", "not_null")], "output")
    assert result.errors == []


def test_not_null_fails_on_none():
    result = validate_data({"name": None}, [_v("name", "not_null")], "output")
    assert len(result.errors) == 1
    assert "null" in result.errors[0]


def test_not_null_fails_on_missing_field():
    result = validate_data({}, [_v("name", "not_null")], "output")
    assert len(result.errors) == 1


# --- not_empty ---

def test_not_empty_passes():
    result = validate_data({"items": [1, 2]}, [_v("items", "not_empty")], "output")
    assert result.errors == []


def test_not_empty_fails_on_empty_string():
    result = validate_data({"name": ""}, [_v("name", "not_empty")], "output")
    assert len(result.errors) == 1


def test_not_empty_fails_on_empty_list():
    result = validate_data({"items": []}, [_v("items", "not_empty")], "output")
    assert len(result.errors) == 1


def test_not_empty_fails_on_none():
    result = validate_data({"x": None}, [_v("x", "not_empty")], "output")
    assert len(result.errors) == 1


# --- min_length ---

def test_min_length_passes():
    result = validate_data({"name": "Adele"}, [_v("name", "min_length", value="3")], "output")
    assert result.errors == []


def test_min_length_fails():
    result = validate_data({"name": "AB"}, [_v("name", "min_length", value="3")], "output")
    assert len(result.errors) == 1


# --- regex ---

def test_regex_passes():
    result = validate_data({"email": "a@b.com"}, [_v("email", "regex", value=r"@.*\.")], "output")
    assert result.errors == []


def test_regex_fails():
    result = validate_data({"email": "bad"}, [_v("email", "regex", value=r"@.*\.")], "output")
    assert len(result.errors) == 1


# --- type ---

def test_type_str_passes():
    result = validate_data({"name": "Adele"}, [_v("name", "type", value="str")], "output")
    assert result.errors == []


def test_type_int_fails_on_str():
    result = validate_data({"count": "5"}, [_v("count", "type", value="int")], "output")
    assert len(result.errors) == 1


def test_type_list_passes():
    result = validate_data({"items": [1]}, [_v("items", "type", value="list")], "output")
    assert result.errors == []


# --- target filtering ---

def test_input_validations_only_run_for_input():
    """Output validations should be skipped when target='input'."""
    validations = [
        _v("name", "not_null", target="input"),
        _v("result", "not_null", target="output"),
    ]
    result = validate_data({"name": "X"}, validations, "input")
    assert result.errors == []  # output validation skipped


# --- nested field ---

def test_nested_field_access():
    data = {"results": [{"lat": 51.5}]}
    result = validate_data(data, [_v("results.0.lat", "not_null")], "output")
    assert result.errors == []


# --- custom message ---

def test_custom_message():
    result = validate_data({"x": None}, [_v("x", "not_null", message="Celebrity not found")], "output")
    assert result.errors == ["Celebrity not found"]


# --- multiple validations ---

def test_multiple_failures_collected():
    validations = [
        _v("a", "not_null"),
        _v("b", "not_null"),
    ]
    result = validate_data({"a": None, "b": None}, validations, "output")
    assert len(result.errors) == 2


# --- unknown check ---

def test_unknown_check_returns_error():
    result = validate_data({"x": 1}, [_v("x", "bogus_check")], "output")
    assert len(result.errors) == 1
    assert "Unknown check" in result.errors[0]


# --- non-critical (warnings) ---

def test_non_critical_goes_to_warnings():
    result = validate_data({"x": None}, [_v("x", "not_null", critical=False)], "output")
    assert result.errors == []
    assert len(result.warnings) == 1
    assert "null" in result.warnings[0]


def test_mixed_critical_and_non_critical():
    validations = [
        _v("a", "not_null", critical=True),
        _v("b", "not_null", critical=False),
    ]
    result = validate_data({"a": None, "b": None}, validations, "output")
    assert len(result.errors) == 1
    assert len(result.warnings) == 1


def test_non_critical_custom_message():
    result = validate_data({"x": None}, [_v("x", "not_null", critical=False, message="Optional field missing")], "output")
    assert result.warnings == ["Optional field missing"]
