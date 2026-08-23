from blastradius.models import HistoricalEvidence, Evidence


class HistoryAnalyzer:
    def analyze(self, pr, records) -> list[HistoricalEvidence]:
        words = {word for word in (pr.title + " " + pr.body + " " + pr.diff).lower().replace("_", " ").split() if len(word.strip(".,:;()[]")) > 3}
        results = []
        for r in records:
            memory_text = " ".join([r.title, r.description, r.outcome, *r.tags, *r.affected_components]).lower().replace("_", " ")
            overlap = sorted(word for word in words if word.strip(".,:;()[]") in memory_text)
            if overlap:
                similarity = min(95, 40 + 15 * len(overlap))
                results.append(HistoricalEvidence(source_type=r.type, source_id=r.id, title=r.title, date=r.date, description=r.description, similarity=similarity, outcome=r.outcome, relevance="Shared terms: " + ", ".join(overlap[:4]) + ".", evidence=[Evidence(source="memory", reference=r.source, claim=r.description), Evidence(source="memory", reference=r.source, claim=f"Historical outcome: {r.outcome}")]))
        return sorted(results, key=lambda x: x.similarity, reverse=True)
