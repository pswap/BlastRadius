from typing import Callable, TypedDict

from blastradius.models import (
    AffectedComponent, AnalysisClaim, BlastRadiusReport, HistoricalEvidence,
    MemoryRecord, PullRequest, RecommendedAction, RiskFactor, RiskLevel,
)


class FailureScenario(TypedDict):
    classification: str
    trigger: str
    behavior: str
    dependency: str
    failure: str
    impact: str
    evidence: list[dict]


class AgentState(TypedDict, total=False):
    owner: str
    repo: str
    number: int
    callback: Callable[[str], None]
    progress: list[str]
    pr: PullRequest
    components: list[AffectedComponent]
    tests: list[AffectedComponent]
    records: list[MemoryRecord]
    history: list[HistoricalEvidence]
    failure_scenarios: list[FailureScenario]
    reasoning_chain: list[str]
    recommended_tests: list[str]
    actions: list[RecommendedAction]
    claims: list[AnalysisClaim]
    score: int
    level: RiskLevel
    factors: list[RiskFactor]
    report: BlastRadiusReport
