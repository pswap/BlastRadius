"""Greptile adapter using the currently documented MCP HTTP transport.

The public Greptile docs currently document MCP transport, ping, tools/list,
and tools/call. They do not document direct codebase query/dependency/caller
operations, so this adapter never guesses a tool name or response schema.
"""
from __future__ import annotations

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
    """Verified adapter for Greptile's documented JSON-RPC MCP endpoint."""
    endpoint = "https://api.greptile.com/mcp"

    def __init__(self, api_key: str, session: requests.Session | Any | None = None):
        self.api_key = api_key.strip()
        self.session = session or requests.Session()

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
            if status in (401, 403): message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access."
            else: message = "Greptile API request failed. Please try again."
            raise GreptileError(message) from exc
        except ValueError as exc:
            raise GreptileError("Greptile returned an unexpected response.") from exc
        if error := body.get("error"):
            message = str(error.get("message", "Greptile MCP request failed."))
            if "auth" in message.lower():
                message = "Greptile authentication or authorization failed. Check GREPTILE_API_KEY access."
            raise GreptileError(message)
        return body.get("result")

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

    @staticmethod
    def _unsupported(operation: str) -> None:
        raise GreptileCapabilityError(
            f"Greptile's current public MCP documentation does not define a supported mapping for {operation}. "
            "No request was sent; use MockGreptileClient in demo mode."
        )

    def query_codebase(self, question: str) -> list[AffectedComponent]: self._unsupported("query_codebase")
    def find_dependencies(self, target: str) -> list[AffectedComponent]: self._unsupported("find_dependencies")
    def find_callers(self, target: str) -> list[AffectedComponent]: self._unsupported("find_callers")
    def find_related_tests(self, target: str) -> list[AffectedComponent]: self._unsupported("find_related_tests")
    def explain_architecture(self, target: str) -> str: self._unsupported("explain_architecture")


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


def get_greptile_client(*, demo_mode: bool, api_key: str) -> GreptileClient:
    return MockGreptileClient() if demo_mode else RealGreptileClient(api_key)
