"""Greptile adapter using documented MCP pull-request review tools only."""
from __future__ import annotations

import json
from typing import Any, Protocol

import requests

from blastradius.models import AffectedComponent, Evidence


class GreptileError(RuntimeError):
    """Safe error suitable for a UI; it deliberately excludes API secrets."""


class GreptileConfigurationError(GreptileError): pass
class GreptileRateLimitError(GreptileError): pass
class GreptileCapabilityError(GreptileError): pass


class GreptileClient(Protocol):
    def set_pull_request_context(self, owner: str, repo: str, number: int, default_branch: str = "main") -> None: ...
    def query_codebase(self, question: str) -> list[AffectedComponent]: ...
    def find_dependencies(self, target: str) -> list[AffectedComponent]: ...
    def find_callers(self, target: str) -> list[AffectedComponent]: ...
    def find_related_tests(self, target: str) -> list[AffectedComponent]: ...
    def explain_architecture(self, target: str) -> str: ...


class RealGreptileClient:
    """Maps BlastRadius operations to Greptile PR review summaries and comments."""
    endpoint = "https://api.greptile.com/mcp"

    def __init__(self, api_key: str, session: requests.Session | Any | None = None, repository: str = ""):
        self.api_key, self.session, self.repository = api_key.strip(), session or requests.Session(), repository.strip()
        self._context: dict[str, Any] | None = None

    @property
    def headers(self) -> dict[str, str]:
        if not self.api_key: raise GreptileConfigurationError("GREPTILE_API_KEY is required when DEMO_MODE=false.")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def set_pull_request_context(self, owner: str, repo: str, number: int, default_branch: str = "main") -> None:
        name = f"{owner}/{repo}"
        if self.repository and self.repository.lower() != name.lower():
            raise GreptileConfigurationError("The configured GREPTILE_REPOSITORY does not match the analyzed GitHub PR.")
        self._context = {"name": name, "remote": "github", "defaultBranch": default_branch, "prNumber": number}

    def _context_arguments(self) -> dict[str, Any]:
        if not self._context:
            raise GreptileConfigurationError("Greptile pull-request context is required before querying review data.")
        return self._context

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None: payload["params"] = params
        try:
            response = self.session.post(self.endpoint, headers=self.headers, json=payload, timeout=20)
            if response.status_code == 429: raise GreptileRateLimitError("Greptile rate limit reached. Please retry later.")
            response.raise_for_status(); body = response.json()
        except GreptileError: raise
        except requests.Timeout as exc: raise GreptileError("Greptile request timed out. Please try again.") from exc
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access." if status in (401, 403) else "Greptile API request failed. Please try again."
            raise GreptileError(message) from exc
        except ValueError as exc: raise GreptileError("Greptile returned an unexpected response.") from exc
        if not isinstance(body, dict): raise GreptileError("Greptile returned an unexpected response.")
        if error := body.get("error"):
            message, lower = str(error.get("message", "Greptile MCP request failed.")), str(error.get("message", "")).lower()
            if error.get("code") == 429 or "rate limit" in lower: raise GreptileRateLimitError("Greptile rate limit reached. Please retry later.")
            if "auth" in lower or "unauthorized" in lower or "forbidden" in lower: message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access."
            raise GreptileError(message)
        return body.get("result")

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._call("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result, dict) and "content" in result:
            for item in result["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    try: parsed = json.loads(item.get("text", ""))
                    except ValueError as exc: raise GreptileError("Greptile returned an unexpected tool response.") from exc
                    if isinstance(parsed, dict): return parsed
        if isinstance(result, dict): return result
        raise GreptileError("Greptile returned an unexpected tool response.")

    def verify_connection(self) -> bool: self._call("ping"); return True
    def list_tools(self) -> list[dict[str, Any]]:
        result = self._call("tools/list") or {}; tools = result.get("tools", [])
        if not isinstance(tools, list): raise GreptileError("Greptile returned an unexpected tools/list response.")
        return tools

    def _review(self) -> dict[str, Any]:
        result = self._call_tool("get_merge_request", self._context_arguments())
        review = result.get("mergeRequest", result)
        if not isinstance(review, dict): raise GreptileError("Greptile returned an unexpected pull-request review response.")
        return review

    def _comments(self, *, addressed: bool | None = None) -> list[dict[str, Any]]:
        arguments = dict(self._context_arguments())
        if addressed is not None: arguments["addressed"] = addressed
        result = self._call_tool("list_merge_request_comments", arguments)
        comments = result.get("comments", [])
        if not isinstance(comments, list): raise GreptileError("Greptile returned an unexpected review-comments response.")
        return [comment for comment in comments if isinstance(comment, dict)]

    def query_codebase(self, question: str) -> list[AffectedComponent]:
        review = self._review()
        summary = next((str(review[key]).strip() for key in ("summary", "description", "body") if isinstance(review.get(key), str) and review[key].strip()), "")
        code_reviews = review.get("codeReviews", [])
        status = ", ".join(str(item.get("status", "unknown")) for item in code_reviews if isinstance(item, dict))
        claim = summary or f"Greptile review status: {status or 'review data retrieved'}"
        return [AffectedComponent(name=f"PR #{self._context_arguments()['prNumber']}", type="pull request review", relationship="Greptile review summary", confidence=.70, evidence=[Evidence(source="greptile", reference=f"PR #{self._context_arguments()['prNumber']}", claim=claim[:500])])]

    def _comment_components(self, target: str, relationship: str, component_type: str = "review comment") -> list[AffectedComponent]:
        target_words = {word.lower() for word in target.split() if len(word) > 2}
        components = []
        for comment in self._comments(addressed=False):
            body = str(comment.get("body", "")).strip(); lower = body.lower()
            if target_words and not any(word in lower for word in target_words): continue
            path, line = str(comment.get("filePath") or "PR review"), comment.get("line") or comment.get("lineNumber")
            reference = f"{path}:{line}" if line else path
            components.append(AffectedComponent(name=path, type=component_type, relationship=relationship, confidence=.70, evidence=[Evidence(source="greptile", reference=reference, claim=body[:500] or "Greptile review comment")]))
        return components

    def find_dependencies(self, target: str) -> list[AffectedComponent]:
        return self._comment_components(target, f"Greptile review comment mentions {target}")
    def find_callers(self, target: str) -> list[AffectedComponent]:
        return self._comment_components(target, f"Greptile review comment mentions {target}")
    def find_related_tests(self, target: str) -> list[AffectedComponent]:
        return self._comment_components(target, f"Greptile review comment mentions test coverage for {target}", "test")
    def explain_architecture(self, target: str) -> str: return "Insufficient evidence: PR-review data does not provide an architecture explanation."


class MockGreptileClient:
    """Offline normalized fixtures for demo mode and tests."""
    def set_pull_request_context(self, owner: str, repo: str, number: int, default_branch: str = "main") -> None: pass
    def _components(self) -> list[AffectedComponent]:
        return [AffectedComponent(name="PaymentService", type="service", relationship="retry behavior changed", confidence=.98, evidence=[Evidence(source="greptile", reference="payments/retry.py", claim="PaymentService publishes a PaymentEvent after retry attempts")]), AffectedComponent(name="payment.events", type="Kafka topic", relationship="receives PaymentEvent", confidence=.95, evidence=[Evidence(source="greptile", reference="payments/events.py", claim="PaymentEvent is published to payment.events")]), AffectedComponent(name="FraudService", type="service", relationship="consumes payment.events", confidence=.92, evidence=[Evidence(source="greptile", reference="fraud/consumer.py", claim="FraudService consumes PaymentEvent from payment.events")]), AffectedComponent(name="NotificationService", type="service", relationship="consumes payment.events", confidence=.90, evidence=[Evidence(source="greptile", reference="notifications/consumer.py", claim="NotificationService consumes PaymentEvent from payment.events")])]
    def query_codebase(self, question: str) -> list[AffectedComponent]: return self._components()
    def find_dependencies(self, target: str) -> list[AffectedComponent]: return self._components()[1:]
    def find_callers(self, target: str) -> list[AffectedComponent]: return []
    def find_related_tests(self, target: str) -> list[AffectedComponent]: return [AffectedComponent(name="test_payment_retry.py", type="test", relationship="covers retry limit", confidence=.85, evidence=[Evidence(source="greptile", reference="tests/test_payment_retry.py", claim="A retry unit test exists but has no idempotency assertion")])]
    def explain_architecture(self, target: str) -> str: return "PaymentService publishes PaymentEvent to payment.events; FraudService and NotificationService consume it."


def get_greptile_client(*, demo_mode: bool, api_key: str, repository: str = "") -> GreptileClient:
    return MockGreptileClient() if demo_mode else RealGreptileClient(api_key, repository=repository)
