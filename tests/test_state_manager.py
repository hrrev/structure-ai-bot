import pytest
from ai_assisted_automation.executor.state_manager import StateManager
from ai_assisted_automation.utils.exceptions import StateResolutionError


def test_resolve_user_input():
    sm = StateManager()
    sm.set_user_inputs({"email": "a@b.com"})
    result = sm.resolve_input_mapping({"e": "$input.email"})
    assert result == {"e": "a@b.com"}


def test_resolve_step_output():
    sm = StateManager()
    sm.store_step_output("step_1", {"account_id": "123"})
    result = sm.resolve_input_mapping({"aid": "step_1.account_id"})
    assert result == {"aid": "123"}


def test_resolve_literal():
    sm = StateManager()
    result = sm.resolve_input_mapping({"region": "us-east-1"})
    assert result == {"region": "us-east-1"}


def test_missing_user_input():
    sm = StateManager()
    sm.set_user_inputs({})
    with pytest.raises(StateResolutionError, match="Missing user input"):
        sm.resolve_input_mapping({"x": "$input.missing"})


def test_missing_step_output():
    sm = StateManager()
    with pytest.raises(StateResolutionError, match="Missing output from step"):
        sm.resolve_input_mapping({"x": "step_99.field"})


def test_nested_dict_access():
    sm = StateManager()
    sm.store_step_output("step_1", {"owner": {"login": "alice"}})
    result = sm.resolve_input_mapping({"user": "step_1.owner.login"})
    assert result == {"user": "alice"}


def test_list_index_access():
    sm = StateManager()
    sm.store_step_output("step_1", {"results": [{"name": "first"}, {"name": "second"}]})
    result = sm.resolve_input_mapping({"val": "step_1.results.0.name"})
    assert result == {"val": "first"}


def test_nested_missing_field_raises():
    sm = StateManager()
    sm.store_step_output("step_1", {"data": {"a": 1}})
    with pytest.raises(StateResolutionError, match="missing field"):
        sm.resolve_input_mapping({"x": "step_1.data.b"})
