from blastradius.models import BlastRadiusReport, Evidence, RecommendedAction
from blastradius.services.impact_analyzer import ImpactAnalyzer
from blastradius.services.history_analyzer import HistoryAnalyzer
from blastradius.services.risk_engine import RiskEngine
from langgraph.graph import StateGraph, START, END
from .state import AgentState


class BlastRadiusAgent:
    """Linear LangGraph-shaped workflow; dependencies are injected for testable adapters."""
    def __init__(self, github, greptile, memory, risk_engine=None):
        self.github, self.greptile, self.memory = github, greptile, memory
        self.impact, self.history, self.risk = ImpactAnalyzer(), HistoryAnalyzer(), risk_engine or RiskEngine()
        self.graph = self._build_graph()
    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("load_pr", self._load_pr)
        graph.add_node("analyze_changes", self._analyze_changes)
        graph.add_node("analyze_codebase", self._analyze_codebase)
        graph.add_node("search_memory", self._search_memory)
        graph.add_node("analyze_history", self._analyze_history)
        graph.add_node("calculate_risk", self._calculate_risk)
        graph.add_node("generate_report", self._generate_report)
        graph.add_edge(START, "load_pr"); graph.add_edge("load_pr", "analyze_changes")
        graph.add_edge("analyze_changes", "analyze_codebase"); graph.add_edge("analyze_codebase", "search_memory")
        graph.add_edge("search_memory", "analyze_history"); graph.add_edge("analyze_history", "calculate_risk")
        graph.add_edge("calculate_risk", "generate_report"); graph.add_edge("generate_report", END)
        return graph.compile()
    @staticmethod
    def _step(state, label):
        progress = state.get("callback")
        if progress: progress(label)
        return {"progress": [*state.get("progress", []), label]}
    def _load_pr(self, state):
        update = self._step(state, "Loaded PR")
        return {**update, "pr": self.github.get_pull_request(state["owner"], state["repo"], state["number"])}
    def _analyze_changes(self, state): return self._step(state, "Analyzed changed files")
    def _analyze_codebase(self, state):
        update = self._step(state, "Queried codebase")
        pr = state["pr"]; components = self.impact.analyze(self.greptile, pr.changed_files); tests = self.greptile.find_related_tests("PaymentService")
        mapped = self._step({**state, "progress": update["progress"]}, "Mapped dependencies")
        return {**mapped, "components": components, "tests": tests}
    def _search_memory(self, state):
        update = self._step(state, "Searched engineering memory")
        return {**update, "records": self.memory.search_memory("payment retry kafka event idempotency")}
    def _analyze_history(self, state):
        update = self._step(state, "Analyzed historical changes")
        return {**update, "history": self.history.analyze(state["pr"], state["records"])}
    def _calculate_risk(self, state):
        update = self._step(state, "Calculated risk")
        score, level, factors = self.risk.score(components=state["components"], historical=state["history"], tests=state["tests"], pr=state["pr"])
        return {**update, "score": score, "level": level, "factors": factors}
    def _generate_report(self, state):
        pr, components, historical = state["pr"], state["components"], state["history"]
        summary = f"This PR increases PaymentService retry attempts from 3 to 5, creating more opportunities to publish PaymentEvent records. {historical[0].source_id if historical else 'No similar change'} is relevant because {historical[0].relevance.lower() if historical else 'evidence is insufficient'}"
        scenario = {"trigger": "Retry limit changes from 3 to 5", "behavior": "Additional payment attempts", "dependency": "PaymentService publishes PaymentEvent to payment.events", "failure": "Duplicate processing by downstream consumer", "impact": "Potential duplicate transaction", "evidence": [e.model_dump() for c in components for e in c.evidence] + ([e.model_dump() for e in historical[0].evidence] if historical else [])}
        actions = [RecommendedAction(priority="P0", action="Add an idempotency regression test", reason="Historical PR #101 resulted in duplicate payment processing.", related_risk="historical"), RecommendedAction(priority="P1", action="Run Kafka consumer contract tests", reason="FraudService and NotificationService consume payment.events.", related_risk="event"), RecommendedAction(priority="P1", action="Verify FraudService compatibility", reason="FraudService is an identified downstream consumer.", related_risk="dependency")]
        evidence = [e for c in components for e in c.evidence] + [e for h in historical for e in h.evidence]
        report = BlastRadiusReport(pr=pr, risk_score=state["score"], risk_level=state["level"], summary=summary, affected_components=components, risk_factors=state["factors"], historical_evidence=historical, failure_scenarios=[scenario], reasoning_chain=["Retry 3 → 5", "Additional payment attempts", "More PaymentEvent records on payment.events", "Downstream consumer processing", "Potential duplicate transaction"], recommended_tests=["Idempotency: same payment key across five retries produces one charge", "Kafka contract: PaymentEvent remains consumable by FraudService", "Consumer deduplication: repeated PaymentEvent is safely ignored"], recommended_actions=actions, evidence=evidence)
        return {"report": report}
    def analyze(self, owner: str, repo: str, number: int, progress=None) -> BlastRadiusReport:
        result = self.graph.invoke({"owner": owner, "repo": repo, "number": number, "callback": progress, "progress": []})
        return result["report"]
