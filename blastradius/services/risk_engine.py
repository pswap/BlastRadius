from dataclasses import dataclass, field
from blastradius.models import RiskFactor, RiskLevel, Evidence


@dataclass
class RiskEngine:
    weights: dict[str, int] = field(default_factory=lambda: {"historical": 25, "event": 20, "api": 15, "dependency": 15, "data": 15, "testing": 10, "external": 10, "reliability": 10})
    def score(self, *, components, historical, tests, pr):
        text = (pr.title + " " + pr.body + " " + pr.diff).lower()
        factors = []
        def add(category, explanation, evidence): factors.append(RiskFactor(category=category, severity="high" if self.weights[category] >= 15 else "medium", score=self.weights[category], explanation=explanation, evidence=evidence))
        incident = next((h for h in historical if "duplicate" in h.outcome.lower() or "failed" in h.outcome.lower()), None)
        if incident: add("historical", f"Similar historical change {incident.source_id} had outcome: {incident.outcome}", incident.evidence)
        if any(c.type == "Kafka topic" for c in components) or "event" in text: add("event", "The changed retry path publishes events to downstream consumers.", [e for c in components for e in c.evidence if c.type == "Kafka topic"])
        downstream = [c for c in components if c.type == "service"]
        if len(downstream) >= 3: add("dependency", f"{len(downstream)} services are affected, including downstream event consumers.", [e for c in downstream for e in c.evidence])
        if "retry" in text or "payment" in text: add("reliability", "Retry behavior is reliability-sensitive and can increase repeated processing.", [Evidence(source="github", reference=f"PR #{pr.number}", claim="PR changes payment retry behavior")])
        if not tests or "idempotency" not in " ".join(c.relationship for c in tests).lower(): add("testing", "No evidence of an idempotency regression assertion was found.", [Evidence(source="greptile", reference="related tests", claim="Insufficient evidence of idempotency test coverage")])
        total = min(100, sum(x.score for x in factors))
        level = RiskLevel.LOW if total < 30 else RiskLevel.MEDIUM if total < 60 else RiskLevel.HIGH if total < 80 else RiskLevel.CRITICAL
        return total, level, factors
