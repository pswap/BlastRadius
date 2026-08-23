from blastradius.demo import demo_agent
from blastradius.memory import MemoryStore
from blastradius.demo import demo_pr
from blastradius.tools import MockGitHubClient, MockGreptileClient
from blastradius.agent import BlastRadiusAgent

def test_agent_report_is_evidence_backed():
    report = demo_agent().analyze("acme", "payments", 123)
    assert report.historical_evidence[0].source_id == "PR-101"
    assert report.evidence
    assert report.failure_scenarios[0]["evidence"]
    assert {claim.classification for claim in report.claims} >= {"FACT", "INFERENCE"}
    assert all(claim.evidence for claim in report.claims)
    assert all(action.evidence for action in report.recommended_actions)


def test_agent_marks_missing_history_as_unknown_and_logs_steps(caplog):
    caplog.set_level("INFO")
    report = BlastRadiusAgent(MockGitHubClient(demo_pr()), MockGreptileClient(), MemoryStore()).analyze("acme", "payments", 123)
    assert any(claim.classification == "UNKNOWN" for claim in report.claims)
    assert "BlastRadius step: Loaded PR" in caplog.text
