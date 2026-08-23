from typing import Protocol
import requests
from blastradius.models import AffectedComponent, Evidence


class GreptileClient(Protocol):
    def query_codebase(self, question: str) -> list[AffectedComponent]: ...
    def find_dependencies(self, target: str) -> list[AffectedComponent]: ...
    def find_callers(self, target: str) -> list[AffectedComponent]: ...
    def find_related_tests(self, target: str) -> list[AffectedComponent]: ...
    def explain_architecture(self, target: str) -> str: ...


class RealGreptileClient:
    """Adapter boundary. Greptile's API evolves; configure endpoint only after verifying docs."""
    def __init__(self, api_key: str): self.api_key = api_key
    def _unavailable(self): raise RuntimeError("Greptile live integration requires a verified current API configuration. Use DEMO_MODE for the offline demo.")
    def query_codebase(self, question): return self._unavailable()
    def find_dependencies(self, target): return self._unavailable()
    def find_callers(self, target): return self._unavailable()
    def find_related_tests(self, target): return self._unavailable()
    def explain_architecture(self, target): return self._unavailable()


class MockGreptileClient:
    def _components(self):
        return [
            AffectedComponent(name="PaymentService", type="service", relationship="retry behavior changed", confidence=.98, evidence=[Evidence(source="greptile", reference="payments/retry.py", claim="PaymentService publishes a PaymentEvent after retry attempts")]),
            AffectedComponent(name="payment.events", type="Kafka topic", relationship="receives PaymentEvent", confidence=.95, evidence=[Evidence(source="greptile", reference="payments/events.py", claim="PaymentEvent is published to payment.events")]),
            AffectedComponent(name="FraudService", type="service", relationship="consumes payment.events", confidence=.92, evidence=[Evidence(source="greptile", reference="fraud/consumer.py", claim="FraudService consumes PaymentEvent from payment.events")]),
            AffectedComponent(name="NotificationService", type="service", relationship="consumes payment.events", confidence=.90, evidence=[Evidence(source="greptile", reference="notifications/consumer.py", claim="NotificationService consumes PaymentEvent from payment.events")]),
        ]
    def query_codebase(self, question): return self._components()
    def find_dependencies(self, target): return self._components()[1:]
    def find_callers(self, target): return []
    def find_related_tests(self, target): return [AffectedComponent(name="test_payment_retry.py", type="test", relationship="covers retry limit", confidence=.85, evidence=[Evidence(source="greptile", reference="tests/test_payment_retry.py", claim="A retry unit test exists but has no idempotency assertion")])]
    def explain_architecture(self, target): return "PaymentService publishes PaymentEvent to payment.events; FraudService and NotificationService consume it."
