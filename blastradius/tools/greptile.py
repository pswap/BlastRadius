"""Greptile adapter using the currently documented MCP HTTP transport."""
from __future__ import annotations

import json
from typing import Any, Protocol

import requests

from blastradius.models import AffectedComponent, Evidence


class GreptileError(RuntimeError):
    """Safe error suitable for a UI; it deliberately excludes API secrets."""


class GreptileConfigurationError(GreptileError):
    pass


class GreptileRateLimitError(GreptileError):
    pass


class GreptileCapabilityError(GreptileError):
    pass


class GreptileClient(Protocol):
    def query_codebase(self, question: str) -> list[AffectedComponent]: ...
    def find_dependencies(self, target: str) -> list[AffectedComponent]: ...
    def find_callers(self, target: str) -> list[AffectedComponent]: ...
    def find_related_tests(self, target: str) -> list[AffectedComponent]: ...
    def explain_architecture(self, target: str) -> str: ...


class RealGreptileClient:
    """Maps BlastRadius operations onto Greptile's documented MCP KB tools."""
    endpoint = "https://api.greptile.com/mcp"

    def __init__(
        self,
        api_key: str,
        session: requests.Session | Any | None = None,
        repository: str = "",
    ):
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        self.repository = repository.strip()
        self._repo_namespace_id: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        if not self.api_key:
            raise GreptileConfigurationError("GREPTILE_API_KEY is required when DEMO_MODE=false.")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            response = self.session.post(self.endpoint, headers=self.headers, json=payload, timeout=20)
            if response.status_code == 429:
                raise GreptileRateLimitError("Greptile rate limit reached. Please retry later.")
            response.raise_for_status()
            body = response.json()
        except GreptileError:
            raise
        except requests.Timeout as exc:
            raise GreptileError("Greptile request timed out. Please try again.") from exc
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (401, 403):
                message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access."
            else:
                message = "Greptile API request failed. Please try again."
            raise GreptileError(message) from exc
        except ValueError as exc:
            raise GreptileError("Greptile returned an unexpected response.") from exc
        if not isinstance(body, dict):
            raise GreptileError("Greptile returned an unexpected response.")
        if error := body.get("error"):
            code = error.get("code")
            message = str(error.get("message", "Greptile MCP request failed."))
            lower = message.lower()
            if code == 429 or "rate limit" in lower or "too many requests" in lower:
                raise GreptileRateLimitError("Greptile rate limit reached. Please retry later.")
            if "auth" in lower or "unauthorized" in lower or "forbidden" in lower:
                message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access."
            raise GreptileError(message)
        return body.get("result")

    def _call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        if isinstance(result, dict) and "content" in result:
            return self._unwrap_mcp_content(result)
        if isinstance(result, dict):
            return result
        raise GreptileError("Greptile returned an unexpected tool response.")

    @staticmethod
    def _unwrap_mcp_content(result: dict[str, Any]) -> dict[str, Any]:
        """Accepts standard MCP text content when Greptile returns that wrapper."""
        content = result.get("content")
        if not isinstance(content, list):
            raise GreptileError("Greptile returned an unexpected tool response.")
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", ""))
                except ValueError as exc:
                    raise GreptileError("Greptile returned an unexpected tool response.") from exc
                if isinstance(parsed, dict):
                    return parsed
        raise GreptileError("Greptile returned an unexpected tool response.")

    def verify_connection(self) -> bool:
        """Uses the documented JSON-RPC ping request."""
        self._call("ping")
        return True

    def list_tools(self) -> list[dict[str, Any]]:
        """Uses MCP discovery; useful for diagnosing enabled Greptile capabilities."""
        result = self._call("tools/list") or {}
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise GreptileError("Greptile returned an unexpected tools/list response.")
        return tools

    def _repository_namespace_id(self) -> str:
        if self._repo_namespace_id:
            return self._repo_namespace_id
        result = self._call_tool("list_knowledge_bases", {"limit": 100})
        repositories = result.get("repositories", [])
        if not isinstance(repositories, list):
            raise GreptileError("Greptile returned an unexpected knowledge-base response.")
        if self.repository:
            selected = next(
                (repo for repo in repositories if repo.get("repoName", "").lower() == self.repository.lower()),
                None,
            )
            if not selected:
                raise GreptileCapabilityError(
                    f"Greptile knowledge base was not found for {self.repository}. "
                    "Confirm the repository is indexed and enabled for Knowledge Base access."
                )
        elif len(repositories) == 1:
            selected = repositories[0]
        else:
            raise GreptileConfigurationError(
                "GREPTILE_REPOSITORY or GITHUB_OWNER/GITHUB_REPO is required when multiple Greptile knowledge bases are visible."
            )
        repo_id = selected.get("repoNamespaceExternalId")
        if not isinstance(repo_id, str) or not repo_id:
            raise GreptileError("Greptile returned an unexpected knowledge-base response.")
        self._repo_namespace_id = repo_id
        return repo_id

    @staticmethod
    def _query(text: str) -> str:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Greptile query must contain at least two characters.")
        return cleaned[:200]

    def _search_knowledge_base(self, query: str, limit: int = 10) -> dict[str, Any]:
        return self._call_tool(
            "search_knowledge_base",
            {
                "repoNamespaceExternalId": self._repository_namespace_id(),
                "query": self._query(query),
                "sections": ["docs", "reverts"],
                "limit": limit,
            },
        )

    def _knowledge_components(
        self,
        *,
        query: str,
        relationship: str,
        component_type: str = "knowledge base",
    ) -> list[AffectedComponent]:
        result = self._search_knowledge_base(query)
        matches = result.get("results", [])
        if not isinstance(matches, list):
            raise GreptileError("Greptile returned an unexpected knowledge-base search response.")
        components: list[AffectedComponent] = []
        for item in matches:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "knowledge-base")
            evidence = self._evidence_from_matches(path, query, item.get("matches", []))
            if evidence:
                components.append(
                    AffectedComponent(
                        name=path,
                        type=component_type,
                        relationship=relationship,
                        confidence=0.70,
                        evidence=evidence,
                    )
                )
        return components

    @staticmethod
    def _evidence_from_matches(path: str, query: str, matches: Any) -> list[Evidence]:
        if not isinstance(matches, list):
            return []
        evidence: list[Evidence] = []
        for match in matches:
            if not isinstance(match, dict):
                continue
            line = match.get("lineNumber")
            reference = f"{path}:{line}" if line else path
            snippet = str(match.get("snippet") or "").strip()
            claim = f"Knowledge base match for '{query}': {snippet or 'matched document'}"
            evidence.append(Evidence(source="greptile", reference=reference, claim=claim[:500]))
        return evidence

    def _list_knowledge_base_documents(self) -> dict[str, Any]:
        return self._call_tool(
            "list_knowledge_base_documents",
            {"repoNamespaceExternalId": self._repository_namespace_id(), "limit": 100},
        )

    def _get_knowledge_base_document(self, path: str) -> str:
        result = self._call_tool(
            "get_knowledge_base_document",
            {"repoNamespaceExternalId": self._repository_namespace_id(), "path": path},
        )
        document = result.get("document", {})
        if not isinstance(document, dict):
            raise GreptileError("Greptile returned an unexpected knowledge-base document response.")
        content = document.get("content")
        if not isinstance(content, str):
            raise GreptileError("Greptile returned an unexpected knowledge-base document response.")
        return content

    def query_codebase(self, question: str) -> list[AffectedComponent]:
        return self._knowledge_components(
            query=question,
            relationship="Greptile knowledge base result for codebase question",
        )

    def find_dependencies(self, target: str) -> list[AffectedComponent]:
        return self._knowledge_components(
            query=f"{target} dependencies imports consumers downstream",
            relationship=f"Greptile knowledge base result for dependencies of {target}",
        )

    def find_callers(self, target: str) -> list[AffectedComponent]:
        return self._knowledge_components(
            query=f"{target} callers call sites usages references",
            relationship=f"Greptile knowledge base result for callers of {target}",
        )

    def find_related_tests(self, target: str) -> list[AffectedComponent]:
        return self._knowledge_components(
            query=f"{target} tests test coverage specs",
            relationship=f"Greptile knowledge base result for tests related to {target}",
            component_type="test",
        )

    def explain_architecture(self, target: str) -> str:
        documents = self._list_knowledge_base_documents()
        paths = documents.get("documentPaths", [])
        if isinstance(paths, list) and "index.md" in paths:
            return self._get_knowledge_base_document("index.md")
        results = self._search_knowledge_base(f"{target} architecture", limit=5).get("results", [])
        snippets = [
            str(match.get("snippet", "")).strip()
            for item in results if isinstance(item, dict)
            for match in item.get("matches", []) if isinstance(match, dict)
            if str(match.get("snippet", "")).strip()
        ]
        return "\n\n".join(snippets) if snippets else "Insufficient evidence"


class MockGreptileClient:
    """Offline normalized fixtures for demo mode and tests."""
    def _components(self) -> list[AffectedComponent]:
        return [
            AffectedComponent(name="PaymentService", type="service", relationship="retry behavior changed", confidence=.98, evidence=[Evidence(source="greptile", reference="payments/retry.py", claim="PaymentService publishes a PaymentEvent after retry attempts")]),
            AffectedComponent(name="payment.events", type="Kafka topic", relationship="receives PaymentEvent", confidence=.95, evidence=[Evidence(source="greptile", reference="payments/events.py", claim="PaymentEvent is published to payment.events")]),
            AffectedComponent(name="FraudService", type="service", relationship="consumes payment.events", confidence=.92, evidence=[Evidence(source="greptile", reference="fraud/consumer.py", claim="FraudService consumes PaymentEvent from payment.events")]),
            AffectedComponent(name="NotificationService", type="service", relationship="consumes payment.events", confidence=.90, evidence=[Evidence(source="greptile", reference="notifications/consumer.py", claim="NotificationService consumes PaymentEvent from payment.events")]),
        ]
    def query_codebase(self, question: str) -> list[AffectedComponent]: return self._components()
    def find_dependencies(self, target: str) -> list[AffectedComponent]: return self._components()[1:]
    def find_callers(self, target: str) -> list[AffectedComponent]: return []
    def find_related_tests(self, target: str) -> list[AffectedComponent]:
        return [AffectedComponent(name="test_payment_retry.py", type="test", relationship="covers retry limit", confidence=.85, evidence=[Evidence(source="greptile", reference="tests/test_payment_retry.py", claim="A retry unit test exists but has no idempotency assertion")])]
    def explain_architecture(self, target: str) -> str: return "PaymentService publishes PaymentEvent to payment.events; FraudService and NotificationService consume it."


def get_greptile_client(*, demo_mode: bool, api_key: str, repository: str = "") -> GreptileClient:
    return MockGreptileClient() if demo_mode else RealGreptileClient(api_key, repository=repository)
