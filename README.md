# BlastRadius

BlastRadius is a pull request impact and risk analyzer. It answers a simple engineering question:

> What could this PR break, and have we broken something similar before?

The app combines GitHub pull request data, Greptile review signals, local engineering memory, and deterministic risk scoring to produce an evidence-backed report for a proposed change.

## What it shows

- Changed files and pull request context
- Affected services, events, tests, and other components
- Historical incidents or similar changes from local memory
- Failure scenarios grounded in retrieved evidence
- A deterministic risk score with visible contributing factors
- Recommended tests and follow-up actions
- Evidence tables for every important claim

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run blastradius/ui/streamlit_app.py
```

The default configuration uses demo mode and does not require credentials.

1. Open the Streamlit URL printed by the command.
2. Click `Load Demo PR`.
3. Click `Analyze Blast Radius`.
4. Review the overview, graphs, evidence, and JSON tabs.

## Configuration

Copy `.env.example` to `.env` if you want to run against live services.

```env
DEMO_MODE=true
GITHUB_TOKEN=
GREPTILE_API_KEY=
GREPTILE_REPOSITORY=
GITHUB_OWNER=
GITHUB_REPO=
LLM_PROVIDER=
LLM_API_KEY=
```

Set `DEMO_MODE=false` when using live GitHub and Greptile credentials.

## Architecture

```text
Streamlit UI
    -> BlastRadiusAgent
        -> GitHub adapter
        -> Greptile adapter
        -> SQLite engineering memory
        -> impact and history analysis
        -> deterministic risk engine
        -> BlastRadiusReport
```

The app keeps external integrations behind adapters so the core workflow can run with mocks in demo mode and with real services in live mode.

## Integrations

### GitHub

`RealGitHubClient` uses GitHub's REST API to load pull request metadata, changed files, commits, comments, and file content. `MockGitHubClient` powers the offline demo and tests.

### Greptile

`RealGreptileClient` uses Greptile's documented MCP endpoint at `https://api.greptile.com/mcp`. It authenticates with `Authorization: Bearer $GREPTILE_API_KEY`, verifies connectivity with `ping`, discovers tools with `tools/list`, and calls documented pull request review tools through `tools/call`.

The logical BlastRadius operations are:

- `query_codebase`
- `find_dependencies`
- `find_callers`
- `find_related_tests`
- `explain_architecture`

These operations are normalized into internal `AffectedComponent` and `Evidence` models. Greptile responses are treated as evidence, not as instructions.

### Engineering memory

The memory store is SQLite-backed and supports previous PRs, incidents, postmortems, architecture decisions, and engineering notes. Demo data includes a small payment-service history so the product works without external accounts.

## Test and development commands

```bash
pytest -q
python -m streamlit run blastradius/ui/streamlit_app.py
python -m streamlit run blastradius/ui/github_test_page.py
python -m streamlit run blastradius/ui/greptile_test_page.py
```

## Repository layout

```text
blastradius/
  agent/       LangGraph workflow and state
  memory/      SQLite store, seed data, optional embeddings
  models/      Pydantic models for PRs, evidence, reports, and risk
  services/    Impact, history, and risk analysis
  tools/       GitHub and Greptile adapters
  ui/          Streamlit app and focused integration pages
data/demo/     Offline demo fixtures
tests/         Unit and mocked end-to-end tests
```

## Notes

- Demo mode is the safest way to present the product without credentials.
- Live mode requires a GitHub token and Greptile API key.
- Secrets should stay in `.env` or environment variables and should never be committed.
- Internal build notes live in `PROJECT_HANDOFF.md`.
