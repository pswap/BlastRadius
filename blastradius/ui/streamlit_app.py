from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from blastradius.agent import BlastRadiusAgent
from blastradius.config import settings
from blastradius.demo import demo_agent, demo_pr
from blastradius.memory import MemoryStore, seed_demo
from blastradius.tools import RealGitHubClient, get_greptile_client
from blastradius.tools.github import parse_pr_url


DEMO_URL = demo_pr().url

RISK_BADGE = {
    "LOW": ("green", ":material/check_circle:"),
    "MEDIUM": ("yellow", ":material/info:"),
    "HIGH": ("orange", ":material/warning:"),
    "CRITICAL": ("red", ":material/local_fire_department:"),
}

PRIORITY_BADGE = {
    "P0": ("red", ":material/priority_high:"),
    "P1": ("orange", ":material/flag:"),
    "P2": ("blue", ":material/schedule:"),
}

SCENARIO_STAGES = [
    ("trigger", "Trigger", ":material/bolt:"),
    ("behavior", "Changed behavior", ":material/sync:"),
    ("dependency", "Downstream dependency", ":material/account_tree:"),
    ("failure", "Failure mode", ":material/error:"),
    ("impact", "Potential impact", ":material/crisis_alert:"),
]


def load_demo_url():
    st.session_state.url = DEMO_URL
    st.session_state.pop("report", None)
    st.session_state.demo_loaded = True


def quote_dot(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def evidence_rows(report) -> list[dict[str, str]]:
    return [evidence.model_dump() for evidence in report.evidence]


def component_rows(report) -> list[dict[str, object]]:
    return [
        {
            "component": component.name,
            "type": component.type,
            "relationship": component.relationship,
            "confidence": round(component.confidence * 100),
            "evidence": len(component.evidence),
        }
        for component in report.affected_components
    ]


def risk_factor_rows(report) -> list[dict[str, object]]:
    return [
        {
            "category": factor.category,
            "severity": factor.severity,
            "score": factor.score,
            "explanation": factor.explanation,
        }
        for factor in report.risk_factors
    ]


def action_rows(report) -> list[dict[str, str]]:
    return [
        {
            "priority": action.priority,
            "action": action.action,
            "reason": action.reason,
            "risk": action.related_risk,
        }
        for action in report.recommended_actions
    ]


def claim_rows(report) -> list[dict[str, object]]:
    return [
        {
            "basis": claim.classification,
            "claim": claim.claim,
            "evidence": len(claim.evidence),
        }
        for claim in report.claims
    ]


def build_dependency_dot(report) -> str:
    names = [component.name for component in report.affected_components]
    known = {"PaymentService", "payment.events", "FraudService", "NotificationService"}
    if known.issubset(set(names)):
        edges = [
            ("PR change", "PaymentService"),
            ("PaymentService", "payment.events"),
            ("payment.events", "FraudService"),
            ("payment.events", "NotificationService"),
        ]
    else:
        path = ["PR change", *names[:6]]
        edges = list(zip(path, path[1:]))

    lines = [
        "digraph BlastRadius {",
        "  graph [rankdir=LR, bgcolor=transparent, pad=0.3, nodesep=0.55, ranksep=0.75];",
        '  node [shape=box, style="rounded,filled", color="#d9dee8", fillcolor="#f7f9fc", fontname="Inter", fontsize=12, margin="0.15,0.09"];',
        '  edge [color="#778396", penwidth=1.8, arrowsize=0.8];',
    ]
    for source, target in edges:
        lines.append(f"  {quote_dot(source)} -> {quote_dot(target)};")
    lines.append("}")
    return "\n".join(lines)


def render_kpis(report):
    services = sum(component.type == "service" for component in report.affected_components)
    tests = sum(component.type == "test" for component in report.affected_components) + len(report.recommended_tests)
    events = sum("event" in component.type.lower() or "topic" in component.type.lower() for component in report.affected_components)
    trend = [20, 34, 48, 61, 74, report.risk_score]

    with st.container(horizontal=True):
        st.metric(
            "Risk",
            report.risk_level.value,
            f"{report.risk_score}/100",
            border=True,
            chart_data=trend,
            chart_type="line",
        )
        st.metric("Affected components", len(report.affected_components), f"{services} services", border=True)
        st.metric("Historical matches", len(report.historical_evidence), "evidence-backed", border=True)
        st.metric("Test signals", tests, f"{events} event paths", border=True)


def render_summary(report):
    with st.container(border=True):
        st.subheader("Executive summary", anchor=False)
        color, icon = RISK_BADGE.get(report.risk_level.value, ("gray", ":material/info:"))
        st.badge(
            f"{report.risk_level.value} RISK · {report.risk_score}/100",
            color=color,
            icon=icon,
        )
        st.write(report.summary)
        st.progress(report.risk_score, text=f"Risk score: {report.risk_score}/100")

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Affected components", anchor=False)
            rows = component_rows(report)
            if rows:
                st.dataframe(
                    rows,
                    hide_index=True,
                    column_config={
                        "confidence": st.column_config.ProgressColumn(
                            "Confidence",
                            min_value=0,
                            max_value=100,
                            format="%d%%",
                        ),
                    },
                )
            else:
                st.caption("No affected components were identified.")
    with right:
        with st.container(border=True):
            st.subheader("Historical warning", anchor=False)
            if report.historical_evidence:
                item = report.historical_evidence[0]
                st.warning(
                    f"**{item.title}**\n\nSimilarity: **{item.similarity}%**\n\nOutcome: {item.outcome}",
                    icon=":material/warning:",
                )
                st.caption(item.relevance)
            else:
                st.info("Insufficient evidence of a similar historical incident.", icon=":material/info:")


def render_graphs(report):
    risk_rows = risk_factor_rows(report)
    component_counts = Counter(component.type for component in report.affected_components)
    component_type_rows = [{"type": label, "count": count} for label, count in component_counts.items()]
    confidence_rows = [
        {"component": component.name, "confidence": round(component.confidence * 100)}
        for component in report.affected_components
    ]

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True, height="stretch"):
            st.subheader("Risk factor contribution", anchor=False)
            if risk_rows:
                st.bar_chart(pd.DataFrame(risk_rows), x="category", y="score", horizontal=True)
            else:
                st.caption("No risk factors were generated.")
    with right:
        with st.container(border=True, height="stretch"):
            st.subheader("Component mix", anchor=False)
            if component_type_rows:
                st.bar_chart(pd.DataFrame(component_type_rows), x="type", y="count")
            else:
                st.caption("No component types were available.")

    left, right = st.columns([1.2, 0.8], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Dependency path", anchor=False)
            st.graphviz_chart(build_dependency_dot(report))
    with right:
        with st.container(border=True):
            st.subheader("Confidence by component", anchor=False)
            if confidence_rows:
                st.bar_chart(pd.DataFrame(confidence_rows), x="component", y="confidence", horizontal=True)
            else:
                st.caption("No confidence values were available.")


def render_pr_context(report):
    pr = report.pr
    with st.container(border=True):
        st.subheader("Pull request", anchor=False)
        st.markdown(f"**{pr.title}**")
        st.caption(
            f":material/tag: #{pr.number} · :material/person: {pr.author} · "
            f":material/database: {pr.owner}/{pr.repo}"
        )
        if pr.labels:
            st.markdown(" ".join(f":gray-badge[{label}]" for label in pr.labels))
        for changed in pr.changed_files:
            st.markdown(
                f"`{changed.path}` &nbsp; :green[+{changed.additions}] "
                f":red[−{changed.deletions}] &nbsp; :gray[{changed.status}]"
            )
            if changed.patch:
                st.code(changed.patch, language="diff")


def render_failure_scenarios(report):
    if not report.failure_scenarios:
        return
    with st.container(border=True):
        st.subheader("How it could break", anchor=False)
        for scenario in report.failure_scenarios:
            for key, label, icon in SCENARIO_STAGES:
                text = scenario.get(key)
                if text:
                    st.markdown(f"{icon} **{label}** — {text}")
            evidence = scenario.get("evidence", [])
            if evidence:
                with st.expander(
                    f"Evidence trail ({len(evidence)} sources)", icon=":material/link:"
                ):
                    for item in evidence:
                        st.markdown(
                            f":gray-badge[{item['source']}] `{item['reference']}` — {item['claim']}"
                        )


def render_recommendations(report):
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Recommended tests", anchor=False)
            for test in report.recommended_tests:
                st.markdown(f"- {test}")
    with right:
        with st.container(border=True):
            st.subheader("Recommended actions", anchor=False)
            if report.recommended_actions:
                for act in report.recommended_actions:
                    color, icon = PRIORITY_BADGE.get(act.priority, ("gray", ":material/label:"))
                    with st.container(border=True):
                        st.badge(act.priority, color=color, icon=icon)
                        st.markdown(f"**{act.action}**")
                        st.caption(act.reason)
            else:
                st.caption("No actions were generated.")


def render_evidence(report):
    with st.container(border=True):
        st.subheader("Reasoning chain", anchor=False)
        st.write(" → ".join(report.reasoning_chain))

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Claims", anchor=False)
            rows = claim_rows(report)
            if rows:
                st.dataframe(rows, hide_index=True)
            else:
                st.caption("No claims were generated.")
    with right:
        with st.container(border=True):
            st.subheader("Risk factors", anchor=False)
            rows = risk_factor_rows(report)
            if rows:
                st.dataframe(rows, hide_index=True)
            else:
                st.caption("No risk factors were generated.")

    with st.container(border=True):
        st.subheader("Evidence ledger", anchor=False)
        rows = evidence_rows(report)
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.caption("No evidence was attached.")


def render(report):
    render_kpis(report)
    overview, graphs, evidence, raw = st.tabs(
        [
            ":material/dashboard: Overview",
            ":material/query_stats: Graphs",
            ":material/fact_check: Evidence",
            ":material/data_object: JSON",
        ]
    )
    with overview:
        render_pr_context(report)
        render_summary(report)
        render_failure_scenarios(report)
        render_recommendations(report)
    with graphs:
        render_graphs(report)
    with evidence:
        render_evidence(report)
    with raw:
        st.code(report.model_dump_json(indent=2), language="json")


def build_agent(owner: str, repo: str):
    if settings.demo_mode:
        return demo_agent(), "acme", "payments", 123
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is required when DEMO_MODE=false.")
    if not settings.greptile_api_key:
        raise RuntimeError("GREPTILE_API_KEY is required when DEMO_MODE=false.")
    store = MemoryStore("blastradius.db")
    seed_demo(store)
    greptile_repository = settings.greptile_repository or f"{owner}/{repo}"
    agent = BlastRadiusAgent(
        RealGitHubClient(settings.github_token),
        get_greptile_client(
            demo_mode=False,
            api_key=settings.greptile_api_key,
            repository=greptile_repository,
        ),
        store,
    )
    return agent, owner, repo, None


def inject_greptile_styles():
    # Greptile-style section labels: monospace, uppercase, letter-spaced, muted.
    # config.toml can't scope this to section headers alone, so a small style
    # block handles it. Risk-severity colors stay our own identity.
    st.html(
        """
        <style>
          [data-testid="stHeading"] h3 {
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace !important;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            font-size: 12.5px !important;
            font-weight: 600 !important;
            color: #8b857e !important;
            margin-top: 0.35rem;
          }
          [data-testid="stMetricLabel"] {
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-size: 11.5px !important;
          }
        </style>
        """
    )


def main():
    st.set_page_config(page_title="BlastRadius", page_icon="🔥", layout="wide")
    inject_greptile_styles()
    st.title("BlastRadius", anchor=False)
    st.caption("Git shows what changed. BlastRadius shows what could break.")

    st.session_state.setdefault("url", DEMO_URL)
    st.session_state.setdefault("demo_loaded", False)

    with st.container(border=True):
        if settings.demo_mode:
            st.badge("Demo mode", icon=":material/science:", color="blue")
            st.caption("No credentials required. The app uses seeded GitHub, Greptile, and memory data.")
        else:
            st.badge("Live mode", icon=":material/cloud_sync:", color="green")
            st.caption("GitHub and Greptile credentials are read from environment variables.")

        url = st.text_input("GitHub PR URL", key="url")
        with st.container(horizontal=True):
            st.button("Load Demo PR", icon=":material/refresh:", on_click=load_demo_url)
            run = st.button("Analyze Blast Radius", icon=":material/play_arrow:", type="primary")

    if st.session_state.demo_loaded and not st.session_state.get("report"):
        st.success("Demo PR loaded. Click Analyze Blast Radius to generate the report.", icon=":material/check_circle:")

    if run:
        progress = []
        with st.status("Analyzing blast radius…", expanded=True) as status:
            steps = st.empty()

            def update(label):
                progress.append(f":material/check_circle: {label}")
                steps.markdown("\n".join(f"- {step}" for step in progress))

            try:
                owner, repo, number = parse_pr_url(url)
                agent, owner, repo, demo_number = build_agent(owner, repo)
                report = agent.analyze(owner, repo, demo_number or number, update)
                st.session_state.report = report
                st.session_state.demo_loaded = False
                status.update(label="Analysis complete", state="complete", expanded=False)
            except Exception as exc:
                status.update(label="Analysis failed", state="error", expanded=True)
                st.error(f"Analysis could not run: {exc}", icon=":material/error:")

    if report := st.session_state.get("report"):
        render(report)


if __name__ == "__main__":
    main()
