"""Tests for form-encoded body support in api_client."""

from unittest.mock import MagicMock, patch

from ai_assisted_automation.executor.api_client import call
from ai_assisted_automation.models.tool import (
    AuthConfig,
    AuthType,
    RequestConfig,
    ResponseExtractConfig,
    ToolDefinition,
)


def _make_tool(content_type: str = "application/json", **kwargs) -> ToolDefinition:
    return ToolDefinition(
        id="test_tool",
        name="Test Tool",
        base_url="https://example.com",
        method=kwargs.get("method", "POST"),
        path=kwargs.get("path", "/token"),
        auth=kwargs.get("auth", AuthConfig(type=AuthType.NONE)),
        request=RequestConfig(
            body=kwargs.get("body", {"grant_type": "client_credentials"}),
            content_type=content_type,
        ),
        response_extract=kwargs.get(
            "response_extract",
            ResponseExtractConfig(fields={"token": "access_token"}, strict=False),
        ),
    )


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


@patch("ai_assisted_automation.executor.api_client.requests.request")
def test_form_encoded_sends_data_not_json(mock_request):
    """POST with form-urlencoded content_type should use data= kwarg."""
    mock_request.return_value = _mock_response({"access_token": "abc123"})
    tool = _make_tool(content_type="application/x-www-form-urlencoded")

    result = call(tool, {}, {})

    _, kwargs = mock_request.call_args
    assert "data" in kwargs
    assert "json" not in kwargs
    assert kwargs["data"] == {"grant_type": "client_credentials"}
    assert result["token"] == "abc123"


@patch("ai_assisted_automation.executor.api_client.requests.request")
def test_json_content_type_sends_json(mock_request):
    """POST with default JSON content_type should use json= kwarg."""
    mock_request.return_value = _mock_response({"access_token": "abc123"})
    tool = _make_tool(content_type="application/json")

    call(tool, {}, {})

    _, kwargs = mock_request.call_args
    assert "json" in kwargs
    assert "data" not in kwargs


@patch("ai_assisted_automation.executor.api_client.requests.request")
def test_default_content_type_is_json(mock_request):
    """RequestConfig without explicit content_type defaults to JSON."""
    mock_request.return_value = _mock_response({"access_token": "abc123"})
    tool = _make_tool()  # no content_type override → default

    call(tool, {}, {})

    _, kwargs = mock_request.call_args
    assert "json" in kwargs
    assert "data" not in kwargs


@patch("ai_assisted_automation.executor.api_client.requests.request")
def test_spotify_token_flow_mock(mock_request):
    """Integration-style test: Spotify token exchange with basic auth + form body."""
    mock_request.return_value = _mock_response(
        {"access_token": "BQD...xyz", "token_type": "bearer", "expires_in": 3600}
    )

    tool = ToolDefinition(
        id="spotify_token",
        name="Spotify Token Exchange",
        base_url="https://accounts.spotify.com",
        method="POST",
        path="/api/token",
        auth=AuthConfig(type=AuthType.BASIC, username_key="auth_username"),
        request=RequestConfig(
            body={"grant_type": "client_credentials"},
            content_type="application/x-www-form-urlencoded",
        ),
        response_extract=ResponseExtractConfig(
            fields={"access_token": "access_token", "expires_in": "expires_in"}
        ),
    )

    result = call(
        tool,
        {},
        {"auth_username": "my_client_id", "auth_token": "my_client_secret"},
    )

    # Verify basic auth header was sent
    _, kwargs = mock_request.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")

    # Verify form-encoded body
    assert kwargs["data"] == {"grant_type": "client_credentials"}
    assert "json" not in kwargs

    # Verify response extraction
    assert result["access_token"] == "BQD...xyz"
    assert result["expires_in"] == 3600
