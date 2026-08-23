import json
import streamlit as st
from blastradius.tools import MockGitHubClient, RealGitHubClient, get_greptile_client
from blastradius.tools.github import parse_pr_url
from blastradius.memory import MemoryStore, seed_demo
from blastradius.agent import BlastRadiusAgent
from blastradius.config import settings
from blastradius.demo import demo_pr, demo_agent
def render(report):
    st.markdown(f"## 🔥 {report.risk_level.value} &nbsp; {report.risk_score} / 100")
    st.info(report.summary)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Impact")
        for c in report.affected_components: st.write(f"**{c.name}** · {c.type} — {c.relationship}")
    with c2:
        st.subheader("⚠️ Historical warning")
        if report.historical_evidence:
            h = report.historical_evidence[0]; st.warning(f"{h.title}\n\nSimilarity: {h.similarity}%\n\nOutcome: {h.outcome}")
        else: st.write("Insufficient evidence")
    st.subheader("Reasoning chain"); st.write(" → ".join(report.reasoning_chain))
    st.subheader("Recommended tests"); [st.write(f"• {t}") for t in report.recommended_tests]
    st.subheader("Recommended actions"); [st.write(f"**{a.priority}** — {a.action}: {a.reason}") for a in report.recommended_actions]
    with st.expander("Why is this risky?"):
        for f in report.risk_factors: st.write(f"**+{f.score} {f.category}** — {f.explanation}")
    with st.expander("Have we seen this before?"):
        for h in report.historical_evidence: st.write(f"**{h.title} ({h.similarity}%)** — {h.outcome}")
    with st.expander("Evidence"):
        st.json([x.model_dump() for x in report.evidence])
    with st.expander("Report JSON"):
        st.code(report.model_dump_json(indent=2), language="json")

def main():
    st.set_page_config(page_title="BlastRadius", page_icon="🔥", layout="wide")
    st.title("🔥 BlastRadius")
    st.caption("Git shows what changed. BlastRadius shows what could break.")
    if "url" not in st.session_state: st.session_state.url = demo_pr().url
    url = st.text_input("GitHub PR URL", key="url")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Load Demo PR"): st.session_state.url = demo_pr().url; st.rerun()
    with col2:
        run = st.button("Analyze Blast Radius", type="primary")
    if run:
        steps = st.empty()
        progress = []
        def update(label): progress.append("✓ " + label); steps.code("\n".join(progress))
        try:
            owner, repo, number = parse_pr_url(url)
            if settings.demo_mode: agent = demo_agent(); owner, repo, number = "acme", "payments", 123
            else:
                if not settings.github_token: raise RuntimeError("GITHUB_TOKEN is required when DEMO_MODE=false.")
                if not settings.greptile_api_key: raise RuntimeError("GREPTILE_API_KEY is required when DEMO_MODE=false.")
                store = MemoryStore("blastradius.db"); seed_demo(store)
                greptile_repository = settings.greptile_repository or f"{owner}/{repo}"
                agent = BlastRadiusAgent(RealGitHubClient(settings.github_token), get_greptile_client(demo_mode=False, api_key=settings.greptile_api_key, repository=greptile_repository), store)
            report = agent.analyze(owner, repo, number, update)
            st.session_state.report = report
        except Exception as exc: st.error(f"Analysis could not run: {exc}")
    if report := st.session_state.get("report"): render(report)

if __name__ == "__main__": main()
