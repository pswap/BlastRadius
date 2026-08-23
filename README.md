# 🔥 BlastRadius

> Git shows what changed. BlastRadius shows what could break.

BlastRadius is an evidence-backed PR impact and risk analyzer built as a hackathon MVP. Paste a GitHub pull-request URL, and it traces changed behavior through known dependencies, engineering memory, and a deterministic risk engine.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run blastradius/ui/streamlit_app.py
```

The default `DEMO_MODE=true` requires no credentials. Click **Load Demo PR**, then **Analyze Blast Radius**. It analyzes a retry change from 3 to 5 and finds PR #101, which caused duplicate payment processing.

Run the test suite with `pytest -q`.

## GitHub PR inspector (Phase -2)

```bash
python3 -m streamlit run blastradius/ui/github_test_page.py
```

In `DEMO_MODE=true`, this uses the mock client. Set `DEMO_MODE=false` and provide `GITHUB_TOKEN` to inspect a real accessible PR. The page shows title, author, changed files, additions/deletions, and diff. GitHub errors are converted into safe messages; tokens are never logged or displayed.

## Architecture

```text
Streamlit → BlastRadiusAgent → GitHub / Greptile / SQLite Memory
                              → impact + history analysis → RiskEngine → Report
```

The agent workflow is load PR → analyze files → map codebase dependencies → search memory → compare history → calculate deterministic risk → generate evidence-backed scenarios and recommendations. The scoring engine, not an LLM, owns the numerical score.

## Integrations

`GitHubClient` and `GreptileClient` are clean adapter protocols, with mock implementations used by demo/tests. The GitHub adapter uses documented REST endpoints. The Greptile live adapter is intentionally a guarded boundary: configure it only after verifying the current official API documentation, rather than hard-coding unstable endpoints. The rest of the app remains unchanged.

### Greptile (Phase 3)

Greptile's current public docs expose an authenticated MCP endpoint at `https://api.greptile.com/mcp`, using `Authorization: Bearer $GREPTILE_API_KEY`. `RealGreptileClient` uses the documented JSON-RPC MCP methods and Knowledge Base tools:

- `ping` for authentication/connection verification
- `tools/list` for capability discovery
- `tools/call` with `list_knowledge_bases`, `search_knowledge_base`, `list_knowledge_base_documents`, and `get_knowledge_base_document`

BlastRadius maps its logical operations onto Greptile Knowledge Base capabilities:

- `query_codebase(question)` → `search_knowledge_base`
- `find_dependencies(target)` → dependency-focused `search_knowledge_base`
- `find_callers(target)` → caller/usage-focused `search_knowledge_base`
- `find_related_tests(target)` → test-focused `search_knowledge_base`
- `explain_architecture(target)` → `get_knowledge_base_document("index.md")` when available, otherwise an architecture-focused search

Responses are normalized into `AffectedComponent` and `Evidence` models. Greptile Knowledge Base text is treated as untrusted evidence, not executable instructions.

Run the focused Greptile smoke page with:

```bash
python3 -m streamlit run blastradius/ui/greptile_test_page.py
```

In `DEMO_MODE=true`, `MockGreptileClient` supplies normalized evidence and requires no credentials. In real mode, set `DEMO_MODE=false`, `GREPTILE_API_KEY`, and either `GREPTILE_REPOSITORY=owner/repo` or `GITHUB_OWNER` plus `GITHUB_REPO`. You do not need a dummy repository for the offline demo; use a real Greptile-indexed repository only when testing live Greptile behavior.

Engineering memory is SQLite with keyword retrieval (suitable for this MVP). It contains historical PRs #101, #102, #120 and #121. Every report claim uses explicit `source`, `reference`, and `claim` evidence; absent information is reported as insufficient evidence.

### Engineering Memory (Phase 4)

`MemoryStore` initializes a small SQLite schema and supports `add_memory`, `get_memory`, `search_memory`, and `list_memories` for incidents, PRs, postmortems, architecture decisions, and engineering notes. Search is deterministic keyword ranking by default. An application may inject an `EmbeddingProvider`; embeddings are persisted in SQLite and used for cosine-similarity search, with automatic keyword fallback if the provider is unavailable. `seed_demo()` adds PRs #101, #102, #120, and #121.

## MCP mapping

The adapter methods map directly to future MCP tools: `github_get_pr`, `github_get_history`, `greptile_query`, `greptile_find_dependencies`, `memory_search`, and `memory_get`. This keeps an MCP server optional and out of the critical demo path.

## Configuration

Copy `.env.example` to `.env`. Supported values are `GITHUB_TOKEN`, `GREPTILE_API_KEY`, `GREPTILE_REPOSITORY`, `LLM_API_KEY`, `LLM_PROVIDER`, `GITHUB_OWNER`, `GITHUB_REPO`, and `DEMO_MODE`. No secrets are stored in this repository.

## Future improvements

Add a verified Greptile production adapter, optional embeddings, a provider-backed LLM explanation layer constrained by supplied evidence, richer GitHub history retrieval, and an MCP server.
