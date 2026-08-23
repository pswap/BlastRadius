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
        event_evidence = [e for c in components for e in c.evidence if c.type == "Kafka topic"]
        if event_evidence or any(term in text for term in ("event", "schema", "message")): add("event", "The change may affect an event or message contract with downstream consumers.", event_evidence or [Evidence(source="github", reference=f"PR #{pr.number}", claim="PR text or diff references an event/message contract")])
        downstream = [c for c in components if c.type == "service"]
        if len(downstream) >= 3: add("dependency", f"{len(downstream)} services are affected, including downstream event consumers.", [e for c in downstream for e in c.evidence])
        reliability_terms = ("retry", "timeout", "backoff", "idempot", "failover", "resilien")
        if any(term in text for term in reliability_terms): add("reliability", "The PR changes a reliability-sensitive behavior.", [Evidence(source="github", reference=f"PR #{pr.number}", claim="PR title, body, or diff contains reliability-sensitive terms")])
        test_text = " ".join([c.relationship + " " + " ".join(e.claim for e in c.evidence) for c in tests]).lower()
        if not tests or any(term in test_text for term in ("no ", "missing", "insufficient")): add("testing", "Related-test evidence does not demonstrate complete regression coverage.", [Evidence(source="greptile", reference="related tests", claim="Insufficient evidence of complete regression test coverage")])
        total = min(100, sum(x.score for x in factors))
        level = RiskLevel.LOW if total < 30 else RiskLevel.MEDIUM if total < 60 else RiskLevel.HIGH if total < 80 else RiskLevel.CRITICAL
        return total, level, factors
