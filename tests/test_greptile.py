import pytest
import requests

from blastradius.models import AffectedComponent
from blastradius.tools.greptile import GreptileConfigurationError, GreptileError, GreptileRateLimitError, MockGreptileClient, RealGreptileClient, get_greptile_client


class Response:
    def __init__(self, payload, status=200): self.payload, self.status_code = payload, status
    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError("failed"); error.response = self; raise error
    def json(self): return self.payload


class Session:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def post(self, url, headers, json, timeout): self.calls.append((url, headers, json)); return self.responses.pop(0)


def result(payload): return Response({"jsonrpc": "2.0", "id": 1, "result": payload})
def context_client(session):
    client = RealGreptileClient("secret", session, repository="owner/repo")
    client.set_pull_request_context("owner", "repo", 42)
    return client


def test_mock_normalizes_components_into_pydantic_models():
    assert all(isinstance(component, AffectedComponent) for component in MockGreptileClient().query_codebase("what changed?"))


def test_demo_mode_selects_mock_and_live_mode_selects_real():
    assert isinstance(get_greptile_client(demo_mode=True, api_key=""), MockGreptileClient)
    assert isinstance(get_greptile_client(demo_mode=False, api_key="key", repository="owner/repo"), RealGreptileClient)


def test_missing_api_key_is_rejected_without_a_request():
    session = Session([])
    with pytest.raises(GreptileConfigurationError): RealGreptileClient("", session).verify_connection()
    assert not session.calls


def test_verified_ping_and_tool_discovery_use_mcp():
    session = Session([result({}), result({"tools": [{"name": "get_merge_request"}]})])
    client = RealGreptileClient("secret", session)
    assert client.verify_connection() is True and client.list_tools() == [{"name": "get_merge_request"}]
    assert [call[2]["method"] for call in session.calls] == ["ping", "tools/list"]
    assert "secret" not in str(session.calls[0][2])


def test_review_summary_uses_get_merge_request_and_normalizes_evidence():
    session = Session([result({"mergeRequest": {"summary": "Changing retry behavior can duplicate events.", "codeReviews": [{"status": "COMPLETED"}]}})])
    components = context_client(session).query_codebase("What changed?")
    assert components[0].type == "pull request review"
    assert components[0].evidence[0].claim == "Changing retry behavior can duplicate events."
    call = session.calls[0][2]
    assert call["params"] == {"name": "get_merge_request", "arguments": {"name": "owner/repo", "remote": "github", "defaultBranch": "main", "prNumber": 42}}


def test_review_comments_back_logical_operations_without_claiming_codebase_access():
    comments = {"comments": [{"body": "PaymentService needs a test for duplicate events.", "filePath": "payments/retry.py", "line": 17}]}
    session = Session([result(comments), result(comments), result(comments)])
    client = context_client(session)
    assert client.find_dependencies("PaymentService")[0].type == "review comment"
    assert client.find_callers("PaymentService")[0].relationship == "Greptile review comment mentions PaymentService"
    assert client.find_related_tests("PaymentService")[0].type == "test"
    assert all(call[2]["params"]["name"] == "list_merge_request_comments" for call in session.calls)
    assert all(call[2]["params"]["arguments"]["addressed"] is False for call in session.calls)


def test_context_is_required_and_repository_mismatch_is_rejected():
    with pytest.raises(GreptileConfigurationError, match="context"):
        RealGreptileClient("key").query_codebase("x")
    with pytest.raises(GreptileConfigurationError, match="does not match"):
        RealGreptileClient("key", repository="other/repo").set_pull_request_context("owner", "repo", 1)


def test_rate_limit_and_auth_errors_are_safe():
    with pytest.raises(GreptileRateLimitError): RealGreptileClient("secret", Session([Response({}, 429)])).verify_connection()
    with pytest.raises(GreptileError, match="authentication or authorization failed") as error:
        RealGreptileClient("secret", Session([Response({"error": {"message": "Authentication failed"}})])).verify_connection()
    assert "secret" not in str(error.value)


def test_architecture_is_unknown_from_review_data_only():
    assert context_client(Session([])).explain_architecture("payments").startswith("Insufficient evidence")
