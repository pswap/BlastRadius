"""Focused screen for inspecting Greptile normalized responses."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from blastradius.config import settings
from blastradius.tools.greptile import GreptileError, get_greptile_client


def render_components(components):
    if not components:
        st.info("No Greptile evidence was returned for this query.")
        return
    st.dataframe(
        [
            {
                "Name": component.name,
                "Type": component.type,
                "Relationship": component.relationship,
                "Confidence": component.confidence,
            }
            for component in components
        ],
        hide_index=True,
    )
    with st.expander("Evidence"):
        st.json([evidence.model_dump() for component in components for evidence in component.evidence])


def main():
    st.set_page_config(page_title="BlastRadius Greptile test", layout="wide")
    st.title("Greptile codebase inspector")
    st.caption("Focused integration test page. API keys are read from the environment and never displayed.")

    repository = st.text_input("Greptile repository", value=settings.greptile_repository or "owner/repo")
    question = st.text_input("Codebase question", value="What depends on PaymentService?")
    operation = st.selectbox(
        "Operation",
        ["query_codebase", "find_dependencies", "find_callers", "find_related_tests", "explain_architecture"],
    )

    if st.button("Ask Greptile", type="primary"):
        try:
            client = get_greptile_client(
                demo_mode=settings.demo_mode,
                api_key=settings.greptile_api_key,
                repository=repository,
            )
            if operation == "query_codebase":
                render_components(client.query_codebase(question))
            elif operation == "find_dependencies":
                render_components(client.find_dependencies(question))
            elif operation == "find_callers":
                render_components(client.find_callers(question))
            elif operation == "find_related_tests":
                render_components(client.find_related_tests(question))
            else:
                st.markdown(client.explain_architecture(question))
        except (GreptileError, ValueError) as exc:
            st.error(str(exc))


if __name__ == "__main__":
    main()
