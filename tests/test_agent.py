from blastradius.demo import demo_agent

def test_agent_report_is_evidence_backed():
    report = demo_agent().analyze("acme", "payments", 123)
    assert report.historical_evidence[0].source_id == "PR-101"
    assert report.evidence
    assert report.failure_scenarios[0]["evidence"]
