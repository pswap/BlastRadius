# Phase 3 Handoff — Greptile Integration

Implement Phase 3 only: Greptile codebase intelligence integration.

## Baseline

- Branch: `main`
- Starting commit: `d949fc0` — Add GitHub PR integration
- Verify before starting: `python3 -m pytest -q`
- Existing GitHub inspector: `python3 -m streamlit run blastradius/ui/github_test_page.py`

## Scope

Implement `RealGreptileClient` in `blastradius/tools/greptile.py` for these logical operations:

- `query_codebase(question)`
- `find_dependencies(target)`
- `find_callers(target)`
- `find_related_tests(target)`
- `explain_architecture(target)`

## Requirements

1. Inspect the current official Greptile API documentation before implementation. Do not invent endpoints, authentication, parameters, or response fields.
2. Keep all Greptile HTTP/API details isolated in `RealGreptileClient`.
3. Preserve `GreptileClient` and `MockGreptileClient`.
4. Normalize live responses into internal Pydantic models, particularly `AffectedComponent` and `Evidence`.
5. Read `GREPTILE_API_KEY` from configuration; never log or display it.
6. Convert API, authentication, and network errors into safe user-facing errors.
7. Keep `DEMO_MODE=true` fully operational without external credentials.
8. Add mocked tests for normalization, every logical operation, URL/request construction, and safe error handling.
9. Add a focused Streamlit Greptile test page (or extend the existing UI) where a user submits a codebase question and sees normalized results.
10. Update the README with Greptile configuration and test instructions.

## Out of Scope

Do not work on engineering memory, historical similarity, risk scoring, LLM reasoning, agent workflow changes, MCP, deployment, or authentication infrastructure.

## Useful Files

- `blastradius/tools/greptile.py`
- `blastradius/models/analysis.py`
- `blastradius/config.py`
- `blastradius/ui/github_test_page.py`
- `tests/test_github.py` (testing reference)
- `.env.example`
- `README.md`

## Completion Checklist

- Install required dependencies.
- Run `python3 -m pytest -q` and fix all failures.
- Run a headless Streamlit smoke test.
- Report changed files, test result, and the Greptile test-page command.
- Do not commit or push unless explicitly asked.
