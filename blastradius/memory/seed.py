from blastradius.models import MemoryRecord


def demo_records() -> list[MemoryRecord]:
    return [
        MemoryRecord(id="PR-101", type="pull_request", title="PR #101: Increase payment retry attempts", description="Changed PaymentService retry behavior. Extra retries emitted additional PaymentEvent records to payment.events.", date="2025-02-10", source="GitHub PR #101", tags=["payment", "retry", "kafka", "idempotency"], affected_components=["PaymentService", "payment.events", "FraudService"], outcome="Duplicate payment processing occurred because additional retries generated duplicate events."),
        MemoryRecord(id="PR-102", type="pull_request", title="PR #102: Add payment idempotency protection", description="Added idempotency protection to the payment processing path.", date="2025-02-18", source="GitHub PR #102", tags=["payment", "idempotency"], affected_components=["PaymentService", "payment.events"], outcome="Prevented duplicate payment processing."),
        MemoryRecord(id="PR-120", type="pull_request", title="PR #120: Change PaymentEvent schema", description="Changed Kafka PaymentEvent schema consumed by FraudService.", date="2025-03-04", source="GitHub PR #120", tags=["payment", "kafka", "event", "schema", "fraud"], affected_components=["PaymentService", "payment.events", "FraudService"], outcome="FraudService failed to consume events."),
        MemoryRecord(id="PR-121", type="pull_request", title="PR #121: Backward-compatible PaymentEvent handling", description="Added backward-compatible PaymentEvent schema handling for FraudService compatibility.", date="2025-03-08", source="GitHub PR #121", tags=["payment", "event", "schema", "compatibility"], affected_components=["PaymentService", "FraudService"], outcome="Resolved the compatibility issue."),
    ]


def seed_demo(store):
    for record in demo_records(): store.add_memory(record)
