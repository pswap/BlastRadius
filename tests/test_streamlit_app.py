from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_load_demo_pr_button_updates_url_without_session_state_error():
    app = AppTest.from_file(ROOT / "blastradius/ui/streamlit_app.py")
    app.run(timeout=15)

    app.button[0].click().run(timeout=15)

    assert not app.exception
    assert app.session_state["url"] == "https://github.com/acme/payments/pull/123"
    assert "Demo PR loaded" in app.success[0].value


def test_analyze_demo_pr_renders_dashboard():
    app = AppTest.from_file(ROOT / "blastradius/ui/streamlit_app.py")
    app.run(timeout=15)

    app.button[1].click().run(timeout=15)

    assert not app.exception
    assert app.session_state["report"].risk_score > 0
    assert app.metric
    assert app.tabs
