"""Evidence-first LangGraph orchestration for a BlastRadius report."""
from __future__ import annotations

import logging
from typing import Callable

from langgraph.graph import END, START, StateGraph

from blastradius.models import AnalysisClaim, BlastRadiusReport, Evidence, RecommendedAction
from blastradius.services.history_analyzer import HistoryAnalyzer
from blastradius.services.impact_analyzer import ImpactAnalyzer
from blastradius.services.risk_engine import RiskEngine
from .state import AgentState

logger = logging.getLogger(__name__)


class BlastRadiusAgent:
    """A deterministic, evidence-first agent; it never fabricates external facts."""
    def __init__(self, github, greptile, memory, risk_engine=None):
        self.github, self.greptile, self.memory = github, greptile, memory
        self.impact, self.history, self.risk = ImpactAnalyzer(), HistoryAnalyzer(), risk_engine or RiskEngine()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        for name, node in [
            ("load_pr", self._load_pr), ("analyze_changes", self._analyze_changes),
            ("analyze_codebase", self._analyze_codebase), ("search_memory", self._search_memory),
            ("analyze_history", self._analyze_history), ("identify_failures", self._identify_failures),
            ("calculate_risk", self._calculate_risk), ("generate_reasoning", self._generate_reasoning),
            ("recommend", self._recommend), ("generate_report", self._generate_report),
        ]: graph.add_node(name, node)
        sequence = ["load_pr", "analyze_changes", "analyze_codebase", "search_memory", "analyze_history", "identify_failures", "calculate_risk", "generate_reasoning", "recommend", "generate_report"]
        graph.add_edge(START, sequence[0])
        for current, following in zip(sequence, sequence[1:]): graph.add_edge(current, following)
        graph.add_edge(sequence[-1], END)
        return graph.compile()

    @staticmethod
    def _step(state: AgentState, label: str) -> dict:
        logger.info("BlastRadius step: %s", label)
        if callback := state.get("callback"): callback(label)
        return {"progress": [*state.get("progress", []), label]}

    def _load_pr(self, state: AgentState):
        update = self._step(state, "Loaded PR")
        return {**update, "pr": self.github.get_pull_request(state["owner"], state["repo"], state["number"])}

    def _analyze_changes(self, state: AgentState): return self._step(state, "Analyzed changed files")

    def _analyze_codebase(self, state: AgentState):
        update = self._step(state, "Queried codebase")
        self.greptile.set_pull_request_context(state["pr"].owner, state["pr"].repo, state["pr"].number)
        components = self.impact.analyze(self.greptile, state["pr"].changed_files)
        target = ", ".join(file.path for file in state["pr"].changed_files) or state["pr"].title
        tests = self.greptile.find_related_tests(target)
        mapped = self._step({**state, "progress": update["progress"]}, "Mapped dependencies")
        return {**mapped, "components": components, "tests": tests}

    def _search_memory(self, state: AgentState):
        update = self._step(state, "Searched engineering memory")
        query = " ".join([state["pr"].title, state["pr"].body, *[file.path for file in state["pr"].changed_files]])
        return {**update, "records": self.memory.search_memory(query)}

    def _analyze_history(self, state: AgentState):
        update = self._step(state, "Analyzed historical changes")
        return {**update, "history": self.history.analyze(state["pr"], state["records"])}

    def _identify_failures(self, state: AgentState):
        update = self._step(state, "Identified failure scenarios")
        component_evidence = [e for component in state["components"] for e in component.evidence]
        historical_evidence = [e for item in state["history"][:1] for e in item.evidence]
        files = ", ".join(file.path for file in state["pr"].changed_files) or "Insufficient evidence"
        dependencies = ", ".join(component.name for component in state["components"]) or "Insufficient evidence"
        if component_evidence and historical_evidence:
            historical = state["history"][0]
            scenario = {"classification": "INFERENCE", "trigger": f"Changes to {files}", "behavior": state["pr"].title, "dependency": f"Identified affected components: {dependencies}", "failure": f"A similar historical change had outcome: {historical.outcome}", "impact": historical.outcome, "evidence": [e.model_dump() for e in component_evidence + historical_evidence]}
            return {**update, "failure_scenarios": [scenario]}
        if component_evidence:
            scenario = {"classification": "UNKNOWN", "trigger": f"Changes to {files}", "behavior": state["pr"].title, "dependency": f"Identified affected components: {dependencies}", "failure": "Insufficient evidence to identify a concrete failure mode.", "impact": "Insufficient evidence to quantify downstream impact.", "evidence": [e.model_dump() for e in component_evidence]}
            return {**update, "failure_scenarios": [scenario]}
        return {**update, "failure_scenarios": []}

    def _calculate_risk(self, state: AgentState):
        update = self._step(state, "Calculated risk")
        score, level, factors = self.risk.score(components=state["components"], historical=state["history"], tests=state["tests"], pr=state["pr"])
        return {**update, "score": score, "level": level, "factors": factors}

    def _generate_reasoning(self, state: AgentState):
        update = self._step(state, "Generated reasoning chain")
        evidence = [e for component in state["components"] for e in component.evidence]
        claims = [AnalysisClaim(classification="FACT", claim=f"PR #{state['pr'].number} changes files: {', '.join(f.path for f in state['pr'].changed_files) or 'Insufficient evidence'}.", evidence=[Evidence(source="github", reference=f"PR #{state['pr'].number}", claim="Changed files returned by GitHub")])]
        claims.extend(AnalysisClaim(classification="FACT", claim=f"{component.name}: {component.relationship}", evidence=component.evidence) for component in state["components"])
        if state["history"]:
            item = state["history"][0]
            claims.append(AnalysisClaim(classification="INFERENCE", claim=f"Historical {item.source_id} is relevant because {item.relevance.lower()}", evidence=item.evidence))
        else:
            claims.append(AnalysisClaim(classification="UNKNOWN", claim="Insufficient evidence of a similar historical change.", evidence=[Evidence(source="memory", reference="search_memory", claim="No matching record was retrieved")]))
        if evidence:
            claims.append(AnalysisClaim(classification="INFERENCE", claim="The changed code may affect the identified components through the documented relationships.", evidence=evidence))
        chain = [f"Changed files: {', '.join(file.path for file in state['pr'].changed_files) or 'Insufficient evidence'}", f"Affected components: {', '.join(component.name for component in state['components']) or 'Insufficient evidence'}", "Historical comparison: " + (state["history"][0].source_id if state["history"] else "Insufficient evidence"), "Risk: deterministic score from evidence-backed factors"]
        return {**update, "reasoning_chain": chain, "claims": claims}

    def _recommend(self, state: AgentState):
        update = self._step(state, "Generated recommendations")
        github_evidence = [Evidence(source="github", reference=f"PR #{state['pr'].number}", claim=f"Changed files: {', '.join(file.path for file in state['pr'].changed_files)}")]
        historical = state["history"][0].evidence if state["history"] else []
        component_evidence = [e for component in state["components"] for e in component.evidence]
        actions = [RecommendedAction(priority="P0", action="Add a regression test for the changed behavior", reason="The PR changes executable code and needs direct regression coverage.", related_risk="testing", evidence=github_evidence)]
        tests = [f"Regression test for changes in {file.path}" for file in state["pr"].changed_files] or ["Add a regression test for the PR behavior"]
        if component_evidence:
            actions.append(RecommendedAction(priority="P1", action="Run targeted contract or integration tests for affected components", reason="Codebase analysis identified components related to the change.", related_risk="dependency", evidence=component_evidence))
            tests.append("Integration test covering: " + ", ".join(component.name for component in state["components"]))
        if historical:
            actions.append(RecommendedAction(priority="P1", action="Add a regression test for the relevant historical outcome", reason="A similar historical change has recorded failure evidence.", related_risk="historical", evidence=historical))
            tests.append("Historical regression: " + state["history"][0].outcome)
        else:
            actions.append(RecommendedAction(priority="P2", action="Review downstream impact before merge", reason="No matching historical outcome was retrieved.", related_risk="unknown", evidence=github_evidence + component_evidence))
        return {**update, "actions": actions, "recommended_tests": tests}

    def _generate_report(self, state: AgentState):
        pr, history = state["pr"], state["history"]
        summary = f"PR #{pr.number} changes {len(pr.changed_files)} file(s). " + (f"Historical {history[0].source_id} is relevant: {history[0].outcome}" if history else "Insufficient evidence of a similar historical incident.")
        evidence = [e for component in state["components"] for e in component.evidence] + [e for item in history for e in item.evidence]
        report = BlastRadiusReport(pr=pr, risk_score=state["score"], risk_level=state["level"], summary=summary, affected_components=state["components"], risk_factors=state["factors"], historical_evidence=history, failure_scenarios=state["failure_scenarios"], reasoning_chain=state["reasoning_chain"], recommended_tests=state["recommended_tests"], recommended_actions=state["actions"], evidence=evidence, claims=state["claims"])
        return {"report": report}

    def analyze(self, owner: str, repo: str, number: int, progress: Callable[[str], None] | None = None) -> BlastRadiusReport:
        result = self.graph.invoke({"owner": owner, "repo": repo, "number": number, "callback": progress, "progress": []})
        return result["report"]
