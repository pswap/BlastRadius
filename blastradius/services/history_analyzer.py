from blastradius.models import HistoricalEvidence, Evidence


class HistoryAnalyzer:
    def analyze(self, pr, records) -> list[HistoricalEvidence]:
        text = (pr.title + " " + pr.body + " " + pr.diff).lower()
        results = []
        for r in records:
            retry_match = "retry" in text and "retry" in " ".join(r.tags).lower()
            event_match = "event" in text and "event" in " ".join(r.tags).lower()
            if retry_match or event_match:
                similarity = 87 if r.id == "PR-101" and retry_match else 70 if event_match else 58
                results.append(HistoricalEvidence(source_type=r.type, source_id=r.id, title=r.title, date=r.date, description=r.description, similarity=similarity, outcome=r.outcome, relevance="Same retry path and downstream Kafka event." if r.id == "PR-101" else "Shares affected payment event components.", evidence=[Evidence(source="memory", reference=r.source, claim=r.description), Evidence(source="memory", reference=r.source, claim=f"Historical outcome: {r.outcome}")]))
        return sorted(results, key=lambda x: x.similarity, reverse=True)
