"""Focused Phase 2 screen for inspecting a GitHub pull request."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from blastradius.config import settings
from blastradius.demo import demo_pr
from blastradius.tools.github import GitHubAPIError, MockGitHubClient, RealGitHubClient, parse_pr_url


def render_pr(pr):
    st.subheader(pr.title); st.caption(f"PR #{pr.number} by **{pr.author}**")
    additions, deletions = sum(f.additions for f in pr.changed_files), sum(f.deletions for f in pr.changed_files)
    c1, c2, c3 = st.columns(3); c1.metric("Changed files", len(pr.changed_files)); c2.metric("Additions", additions); c3.metric("Deletions", deletions)
    st.subheader("Changed files")
    st.dataframe([{"Path": f.path, "Status": f.status, "+": f.additions, "-": f.deletions} for f in pr.changed_files], hide_index=True)
    with st.expander("Diff"): st.code(pr.diff or "No diff supplied by GitHub.", language="diff")


def main():
    st.set_page_config(page_title="BlastRadius · GitHub test", page_icon="🐙", layout="wide")
    st.title("🐙 GitHub PR Inspector")
    st.caption("Phase 2 integration test page. Tokens are never displayed or logged.")
    url = st.text_input("GitHub PR URL", value=demo_pr().url)
    if st.button("Load pull request", type="primary"):
        try:
            owner, repo, number = parse_pr_url(url)
            client = MockGitHubClient(demo_pr()) if settings.demo_mode else RealGitHubClient(settings.github_token)
            render_pr(client.get_pull_request(owner, repo, number))
        except (ValueError, GitHubAPIError) as exc: st.error(str(exc))


if __name__ == "__main__": main()
