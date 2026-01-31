import pytest
import responses

from ai_assisted_automation.executor.api_client import call
from ai_assisted_automation.models.tool import AuthType, ToolDefinition
from ai_assisted_automation.utils.exceptions import StepExecutionError


@responses.activate
def test_get_with_query_params():
    responses.add(responses.GET, "http://api.test.com/data", json={"result": 1}, status=200)
    tool = ToolDefinition(id="t", name="t", base_url="http://api.test.com", path="/data")
    result = call(tool, {"q": "hello"})
    assert result == {"result": 1}
    assert "q=hello" in responses.calls[0].request.url


@responses.activate
def test_post_with_json_body():
    responses.add(responses.POST, "http://api.test.com/submit", json={"id": 42}, status=200)
    tool = ToolDefinition(id="t", name="t", base_url="http://api.test.com", path="/submit", method="POST")
    result = call(tool, {"name": "test"})
    assert result == {"id": 42}


@responses.activate
def test_url_template_substitution():
    responses.add(responses.GET, "http://api.test.com/users/123", json={"name": "Alice"}, status=200)
    tool = ToolDefinition(id="t", name="t", base_url="http://api.test.com", path="/users/{user_id}")
    result = call(tool, {"user_id": "123"})
    assert result == {"name": "Alice"}


@responses.activate
def test_auth_header_api_key():
    responses.add(responses.GET, "http://api.test.com/data", json={}, status=200)
    tool = ToolDefinition(
        id="t", name="t", base_url="http://api.test.com", path="/data",
        auth_type=AuthType.API_KEY, auth_header="X-Key",
    )
    call(tool, {}, {"auth_token": "secret"})
    assert responses.calls[0].request.headers["X-Key"] == "secret"


@responses.activate
def test_auth_header_bearer():
    responses.add(responses.GET, "http://api.test.com/data", json={}, status=200)
    tool = ToolDefinition(
        id="t", name="t", base_url="http://api.test.com", path="/data",
        auth_type=AuthType.BEARER,
    )
    call(tool, {}, {"auth_token": "tok"})
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_non_200_raises():
    responses.add(responses.GET, "http://api.test.com/data", body="Not Found", status=404)
    tool = ToolDefinition(id="t", name="t", base_url="http://api.test.com", path="/data")
    with pytest.raises(StepExecutionError, match="404"):
        call(tool, {})


@responses.activate
def test_non_json_response():
    responses.add(responses.GET, "http://api.test.com/data", body="plain text", status=200)
    tool = ToolDefinition(id="t", name="t", base_url="http://api.test.com", path="/data")
    result = call(tool, {})
    assert result["body"] == "plain text"
    assert result["status_code"] == 200
