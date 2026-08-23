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
    assert isinstance(get_greptile_client(demo_mode=False, api_key="key", repository="owner/repo"), RealGreptileClient)


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


def knowledge_base_response():
    return Response({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "repositories": [
                {"repoNamespaceExternalId": "repo-123", "repoName": "owner/repo"},
            ],
            "total": 1,
            "returned": 1,
        },
    })


def search_response(path="docs/payments.md", snippet="PaymentService publishes PaymentEvent to payment.events"):
    return Response({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "repoNamespaceExternalId": "repo-123",
            "repoName": "owner/repo",
            "query": "PaymentService",
            "sections": ["docs"],
            "results": [
                {
                    "path": path,
                    "section": "docs",
                    "matches": [{"lineNumber": 42, "snippet": snippet}],
                    "moreMatches": False,
                }
            ],
            "total": 1,
            "returned": 1,
            "untrustedContent": True,
        },
    })


def test_query_codebase_maps_to_knowledge_base_search_and_normalizes_results():
    session = Session([knowledge_base_response(), search_response()])
    client = RealGreptileClient("secret", session, repository="owner/repo")

    components = client.query_codebase("PaymentService dependencies")

    assert components == [
        AffectedComponent(
            name="docs/payments.md",
            type="knowledge base",
            relationship="Greptile knowledge base result for codebase question",
            confidence=0.70,
            evidence=[
                {
                    "source": "greptile",
                    "reference": "docs/payments.md:42",
                    "claim": "Knowledge base match for 'PaymentService dependencies': PaymentService publishes PaymentEvent to payment.events",
                }
            ],
        )
    ]
    assert session.calls[0][2]["method"] == "tools/call"
    assert session.calls[0][2]["params"]["name"] == "list_knowledge_bases"
    assert session.calls[1][2]["params"]["name"] == "search_knowledge_base"
    assert session.calls[1][2]["params"]["arguments"]["repoNamespaceExternalId"] == "repo-123"


def test_dependency_caller_and_test_operations_use_targeted_kb_queries():
    session = Session([
        knowledge_base_response(),
        search_response("docs/dependencies.md"),
        search_response("docs/callers.md"),
        search_response("docs/tests.md", "test_payment_retry covers retry behavior"),
    ])
    client = RealGreptileClient("secret", session, repository="owner/repo")

    dependencies = client.find_dependencies("PaymentService")
    callers = client.find_callers("PaymentService")
    tests = client.find_related_tests("PaymentService")

    assert dependencies[0].relationship == "Greptile knowledge base result for dependencies of PaymentService"
    assert callers[0].relationship == "Greptile knowledge base result for callers of PaymentService"
    assert tests[0].type == "test"
    queries = [call[2]["params"]["arguments"]["query"] for call in session.calls[1:]]
    assert "dependencies" in queries[0]
    assert "callers" in queries[1]
    assert "tests" in queries[2]


def test_explain_architecture_reads_index_document_when_available():
    session = Session([
        knowledge_base_response(),
        Response({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "repoNamespaceExternalId": "repo-123",
                "repoName": "owner/repo",
                "indexPresent": True,
                "documentPaths": ["index.md", "docs/payments.md"],
                "total": 2,
                "returned": 2,
            },
        }),
        Response({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "document": {
                    "repoNamespaceExternalId": "repo-123",
                    "repoName": "owner/repo",
                    "path": "index.md",
                    "section": "docs",
                    "versionId": "v1",
                    "characterCount": 31,
                    "content": "# Architecture\nPayment system",
                },
                "untrustedContent": True,
            },
        }),
    ])

    assert RealGreptileClient("secret", session, repository="owner/repo").explain_architecture("payments") == "# Architecture\nPayment system"
    assert session.calls[1][2]["params"]["name"] == "list_knowledge_base_documents"
    assert session.calls[2][2]["params"]["name"] == "get_knowledge_base_document"


def test_repository_selection_requires_a_matching_knowledge_base():
    session = Session([knowledge_base_response()])
    with pytest.raises(GreptileCapabilityError, match="not found"):
        RealGreptileClient("secret", session, repository="other/repo").query_codebase("PaymentService")
