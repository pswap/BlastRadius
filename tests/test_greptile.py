import pytest
import requests

from blastradius.models import AffectedComponent
from blastradius.tools.greptile import (
    GreptileCapabilityError, GreptileConfigurationError, GreptileError,
    GreptileRateLimitError, MockGreptileClient, RealGreptileClient, get_greptile_client,
)


class Response:
    def __init__(self, payload, status=200): self.payload, self.status_code = payload, status
    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError("failed"); error.response = self; raise error
    def json(self): return self.payload


class Session:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def post(self, url, headers, json, timeout): self.calls.append((url, headers, json)); return self.responses.pop(0)


def test_mock_normalizes_components_into_pydantic_models():
    components = MockGreptileClient().query_codebase("what depends on payments?")
    assert all(isinstance(component, AffectedComponent) for component in components)
    assert components[0].evidence[0].source == "greptile"


def test_demo_mode_selects_mock_and_live_mode_selects_real():
    assert isinstance(get_greptile_client(demo_mode=True, api_key=""), MockGreptileClient)
    assert isinstance(get_greptile_client(demo_mode=False, api_key="key"), RealGreptileClient)


def test_missing_api_key_is_rejected_without_a_request():
    session = Session([])
    with pytest.raises(GreptileConfigurationError): RealGreptileClient("", session).verify_connection()
    assert not session.calls


def test_verified_ping_and_tool_discovery_use_documented_mcp_methods():
    session = Session([Response({"jsonrpc": "2.0", "id": 1, "result": {}}), Response({"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "list_custom_context"}]}})])
    client = RealGreptileClient("secret", session)
    assert client.verify_connection() is True
    assert client.list_tools() == [{"name": "list_custom_context"}]
    assert session.calls[0][0] == "https://api.greptile.com/mcp"
    assert session.calls[0][2]["method"] == "ping" and session.calls[1][2]["method"] == "tools/list"
    assert "secret" not in str(session.calls[0][2])


def test_rate_limit_and_auth_errors_are_safe():
    with pytest.raises(GreptileRateLimitError): RealGreptileClient("secret", Session([Response({}, 429)])).verify_connection()
    with pytest.raises(GreptileError, match="authentication or authorization failed") as error:
        RealGreptileClient("secret", Session([Response({"error": {"message": "Authentication failed"}})])).verify_connection()
    assert "secret" not in str(error.value)


def test_undocumented_codebase_operations_are_not_guessed():
    with pytest.raises(GreptileCapabilityError, match="does not define"):
        RealGreptileClient("key").find_dependencies("PaymentService")
