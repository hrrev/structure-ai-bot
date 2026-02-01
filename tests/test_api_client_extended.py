import base64

import pytest
import responses

from ai_assisted_automation.executor.api_client import call
from ai_assisted_automation.models.tool import (
    AuthConfig,
    AuthType,
    RequestConfig,
    ResponseExtractConfig,
    ToolDefinition,
)


def _tool(**kwargs):
    defaults = dict(id="t1", name="test", base_url="https://api.example.com")
    defaults.update(kwargs)
    return ToolDefinition(**defaults)


class TestNewConfigPath:
    @responses.activate
    def test_nested_body_template(self):
        responses.add(
            responses.POST,
            "https://api.example.com/",
            json={"ok": True},
            status=200,
        )
        tool = _tool(
            method="POST",
            request=RequestConfig(
                body={
                    "customer": {"email": "{{email}}", "tier": "{{tier}}"},
                    "metadata": {"source": "automation"},
                },
            ),
        )
        result = call(tool, {"email": "a@b.com", "tier": "gold"})
        body = responses.calls[0].request.body
        import json

        sent = json.loads(body)
        assert sent["customer"]["email"] == "a@b.com"
        assert sent["metadata"]["source"] == "automation"
        assert result == {"ok": True}

    @responses.activate
    def test_query_params_and_body(self):
        responses.add(
            responses.POST,
            "https://api.example.com/",
            json={"created": True},
            status=200,
        )
        tool = _tool(
            method="POST",
            request=RequestConfig(
                query_params=["dry_run"],
                body={"name": "{{name}}"},
            ),
        )
        call(tool, {"dry_run": "true", "name": "Alice"})
        req = responses.calls[0].request
        assert "dry_run=true" in req.url
        import json

        assert json.loads(req.body)["name"] == "Alice"

    @responses.activate
    def test_path_params(self):
        responses.add(
            responses.POST,
            "https://api.example.com/orgs/42/orders",
            json={"id": 1},
            status=200,
        )
        tool = _tool(
            method="POST",
            path="/orgs/{org_id}/orders",
            request=RequestConfig(
                path_params=["org_id"],
                body={"item": "{{item}}"},
            ),
        )
        call(tool, {"org_id": 42, "item": "widget"})
        assert "/orgs/42/orders" in responses.calls[0].request.url

    @responses.activate
    def test_custom_headers(self):
        responses.add(
            responses.POST,
            "https://api.example.com/",
            json={},
            status=200,
        )
        tool = _tool(
            method="POST",
            request=RequestConfig(
                headers={"X-Idempotency-Key": "{{idem_key}}"},
                body={},
            ),
        )
        call(tool, {"idem_key": "abc-123"})
        assert responses.calls[0].request.headers["X-Idempotency-Key"] == "abc-123"

    @responses.activate
    def test_response_extract_strict(self):
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json={"data": {"order": {"id": 99, "status": "paid"}}},
            status=200,
        )
        tool = _tool(
            request=RequestConfig(),
            response_extract=ResponseExtractConfig(
                fields={"order_id": "data.order.id", "status": "data.order.status"},
                strict=True,
            ),
        )
        result = call(tool, {})
        assert result == {"order_id": 99, "status": "paid"}

    @responses.activate
    def test_response_extract_strict_missing_raises(self):
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json={"data": {}},
            status=200,
        )
        tool = _tool(
            request=RequestConfig(),
            response_extract=ResponseExtractConfig(
                fields={"order_id": "data.order.id"},
                strict=True,
            ),
        )
        from ai_assisted_automation.utils.exceptions import StepExecutionError

        with pytest.raises(StepExecutionError, match="extraction failed"):
            call(tool, {})

    @responses.activate
    def test_response_extract_non_strict_returns_none(self):
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json={"data": {}},
            status=200,
        )
        tool = _tool(
            request=RequestConfig(),
            response_extract=ResponseExtractConfig(
                fields={"order_id": "data.order.id"},
                strict=False,
            ),
        )
        result = call(tool, {})
        assert result == {"order_id": None}

    @responses.activate
    def test_graphql_structure(self):
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json={"data": {"repository": {"stargazerCount": 1000}}},
            status=200,
        )
        tool = _tool(
            base_url="https://api.github.com/graphql",
            method="POST",
            auth=AuthConfig(type=AuthType.BEARER),
            request=RequestConfig(
                body={
                    "query": "query($owner: String!) { repository(owner: $owner) { stargazerCount } }",
                    "variables": {"owner": "{{owner}}"},
                },
            ),
            response_extract=ResponseExtractConfig(
                fields={"stars": "data.repository.stargazerCount"},
            ),
        )
        result = call(tool, {"owner": "octocat"}, {"auth_token": "ghp_xxx"})
        assert result == {"stars": 1000}
        assert "Bearer ghp_xxx" in responses.calls[0].request.headers["Authorization"]

    @responses.activate
    def test_basic_auth(self):
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json={"ok": True},
            status=200,
        )
        tool = _tool(
            auth=AuthConfig(type=AuthType.BASIC),
            request=RequestConfig(),
        )
        call(tool, {}, {"auth_username": "user", "auth_token": "pass"})
        expected = base64.b64encode(b"user:pass").decode()
        assert responses.calls[0].request.headers["Authorization"] == f"Basic {expected}"


class TestLegacyBackwardCompat:
    @responses.activate
    def test_legacy_get(self):
        """Tools without request config still use legacy path."""
        responses.add(
            responses.GET,
            "https://api.example.com/data",
            json={"result": 1},
            status=200,
        )
        tool = _tool(path="/data")
        result = call(tool, {"q": "test"})
        assert result == {"result": 1}
        assert "q=test" in responses.calls[0].request.url

    @responses.activate
    def test_legacy_list_wrapping(self):
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json=[1, 2, 3],
            status=200,
        )
        tool = _tool()
        result = call(tool, {})
        assert result == {"items": [1, 2, 3], "count": 3}

    @responses.activate
    def test_new_path_list_wrapping_without_extract(self):
        """New path without response_extract still wraps lists."""
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json=[1, 2],
            status=200,
        )
        tool = _tool(request=RequestConfig())
        result = call(tool, {})
        assert result == {"items": [1, 2], "count": 2}

    @responses.activate
    def test_new_path_list_with_extract_no_wrapping(self):
        """New path with response_extract extracts directly from list."""
        responses.add(
            responses.GET,
            "https://api.example.com/",
            json=[{"id": 1}, {"id": 2}],
            status=200,
        )
        tool = _tool(
            request=RequestConfig(),
            response_extract=ResponseExtractConfig(
                fields={"first_id": "0.id"},
            ),
        )
        result = call(tool, {})
        assert result == {"first_id": 1}
