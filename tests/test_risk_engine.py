from blastradius.demo import demo_agent

def test_deterministic_critical_risk():
    report = demo_agent().analyze("acme", "payments", 123)
    assert report.risk_score == 80
    assert report.risk_level.value == "CRITICAL"
    assert any(f.category == "historical" for f in report.risk_factors)
