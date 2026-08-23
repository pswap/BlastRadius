# BlastRadius project handoff

This file is for internal context. Keep the public README focused on what the product does and how to run it.

## Current state

BlastRadius is a working Streamlit demo for pull request impact analysis.

What works today:

- Offline demo flow with no credentials
- GitHub adapter with real and mock implementations
- Greptile adapter with real and mock implementations
- SQLite engineering memory with seeded history
- LangGraph-based orchestration
- Deterministic risk scoring
- Evidence-backed report model
- Streamlit dashboard with overview, graphs, evidence, and JSON views
- Focused GitHub and Greptile integration test pages
- Pytest coverage for models, adapters, memory, risk, agent flow, and Streamlit behavior

## Build scope

The project was scoped as a hackathon-style MVP: prove the PR impact-analysis workflow, make the demo clear, and keep external systems behind replaceable adapters.

Things intentionally kept simple:

- SQLite instead of a remote database
- Seeded memory instead of a full knowledge platform
- Mock clients for demo mode
- Deterministic scoring instead of model-selected scores
- Streamlit instead of a custom frontend stack
- Adapter boundaries instead of full production integration infrastructure

## Codex workflow

Codex was used as the implementation assistant for repository work:

- Inspect the current code before editing
- Keep changes scoped to the requested area
- Use adapters for external services
- Avoid guessing external API contracts
- Add or update tests with each behavior change
- Run pytest before pushing
- Push small commits with clear messages

When continuing with Codex, start by pulling the latest GitHub state, then work in the actual Git checkout. The downloaded local folder may not be a Git repository.

## Replit and demo scope

The product scope came from a Replit/hackathon-style build prompt: build a polished working demo quickly, not a production platform.

The important demo story is:

1. A user enters or loads a GitHub PR URL.
2. The app collects PR facts.
3. The app asks Greptile for code-review/codebase evidence.
4. The app searches engineering memory for similar historical changes.
5. The agent assembles evidence and failure scenarios.
6. The risk engine calculates a score.
7. The UI presents the risk, affected components, graphs, history, tests, actions, and evidence.

## Demo mode

Demo mode is the primary presentation path.

Use:

```bash
DEMO_MODE=true
streamlit run blastradius/ui/streamlit_app.py
```

The demo uses:

- `data/demo/pr.json`
- `MockGitHubClient`
- `MockGreptileClient`
- SQLite memory seeded from `blastradius/memory/seed.py`

No GitHub or Greptile credentials are needed in demo mode.

## Live mode

Live mode should be used only after adding local environment variables.

```env
DEMO_MODE=false
GITHUB_TOKEN=
GREPTILE_API_KEY=
GREPTILE_REPOSITORY=owner/repo
```

Do not paste secrets into chat logs, commits, screenshots, or docs.

## Useful commands

```bash
source .venv/bin/activate
pytest -q
streamlit run blastradius/ui/streamlit_app.py
streamlit run blastradius/ui/github_test_page.py
streamlit run blastradius/ui/greptile_test_page.py
```

## Verification checklist

Before pushing:

- Run `pytest -q`
- Run or smoke-test the Streamlit app
- Confirm demo mode still works without credentials
- Confirm `.env` is not committed
- Confirm report claims include evidence
- Confirm the risk score is deterministic

## Future work

- Improve live Greptile coverage as documented tools evolve
- Add provider-backed LLM explanation constrained to supplied evidence
- Add richer GitHub history retrieval
- Add optional embeddings for memory search
- Add export/share for reports
