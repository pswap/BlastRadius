from blastradius.demo import demo_agent
from blastradius.memory import MemoryStore
from blastradius.demo import demo_pr
from blastradius.tools import MockGitHubClient, MockGreptileClient
from blastradius.agent import BlastRadiusAgent
from blastradius.models import AffectedComponent, ChangedFile, Evidence, PullRequest

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


class GenericGreptile:
    def set_pull_request_context(self, owner, repo, number, default_branch="main"): pass
    def query_codebase(self, question):
        return [AffectedComponent(name="OrderService", type="service", relationship="consumes order changes", confidence=.9, evidence=[Evidence(source="greptile", reference="orders/consumer.py", claim="OrderService consumes OrderChanged events")])]
    def find_related_tests(self, target): return []


def test_agent_does_not_inherit_payment_demo_language_for_an_unrelated_pr():
    pr = PullRequest(owner="acme", repo="orders", number=9, title="Update order validation", body="Reject invalid country codes.", author="dev", url="https://github.com/acme/orders/pull/9", changed_files=[ChangedFile(path="orders/validation.py", patch="+VALID_COUNTRIES")])
    report = BlastRadiusAgent(MockGitHubClient(pr), GenericGreptile(), MemoryStore()).analyze("acme", "orders", 9)
    text = report.model_dump_json().lower()
    assert "paymentservice" not in text and "fraudservice" not in text
    assert "retry limit changes from 3 to 5" not in text
    assert report.failure_scenarios[0]["classification"] == "UNKNOWN"
    assert any(claim.classification == "UNKNOWN" for claim in report.claims)
