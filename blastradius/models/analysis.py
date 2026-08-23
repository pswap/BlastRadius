from typing import Any, Literal
from pydantic import BaseModel, Field
from .pr import PullRequest
from .risk import RiskLevel


class Evidence(BaseModel):
    source: str
    reference: str
    claim: str


class AnalysisClaim(BaseModel):
    """A report assertion classified by its epistemic basis."""
    classification: Literal["FACT", "INFERENCE", "UNKNOWN"]
    claim: str
    evidence: list[Evidence] = Field(default_factory=list)


class AffectedComponent(BaseModel):
    name: str
    type: str
    relationship: str
    confidence: float
    evidence: list[Evidence] = Field(default_factory=list)


class HistoricalEvidence(BaseModel):
    source_type: str
    source_id: str
    title: str
    date: str
    description: str
    similarity: int
    outcome: str
    relevance: str
    evidence: list[Evidence] = Field(default_factory=list)


class RiskFactor(BaseModel):
    category: str
    severity: str
    score: int
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    priority: str
    action: str
    reason: str
    related_risk: str
    evidence: list[Evidence] = Field(default_factory=list)


class BlastRadiusReport(BaseModel):
    pr: PullRequest
    risk_score: int
    risk_level: RiskLevel
    summary: str
    affected_components: list[AffectedComponent] = Field(default_factory=list)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    historical_evidence: list[HistoricalEvidence] = Field(default_factory=list)
    failure_scenarios: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_chain: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[AnalysisClaim] = Field(default_factory=list)
