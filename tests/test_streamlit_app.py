from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_load_demo_pr_button_updates_url_without_session_state_error():
    app = AppTest.from_file(ROOT / "blastradius/ui/streamlit_app.py")
    app.run()

    app.button[0].click().run()

    assert not app.exception
    assert app.session_state["url"] == "https://github.com/acme/payments/pull/123"
