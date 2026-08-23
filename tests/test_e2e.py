from blastradius.demo import demo_agent

def test_mocked_pr_to_report_flow():
    events = []
    report = demo_agent().analyze("acme", "payments", 123, events.append)
    assert events == ["Loaded PR", "Analyzed changed files", "Queried codebase", "Mapped dependencies", "Searched engineering memory", "Analyzed historical changes", "Identified failure scenarios", "Calculated risk", "Generated reasoning chain", "Generated recommendations"]
    assert report.pr.number == 123
    assert "Duplicate payment processing" in report.historical_evidence[0].outcome
