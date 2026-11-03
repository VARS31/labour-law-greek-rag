# labour-law-greek-rag

Learning project: **agentic RAG over Greek labour law**, fully local.

## Goal

- Scope: **labour law only**, i.e. volume 41 (label id 41, *ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ*) of the Hugging Face
  dataset `AI-team-UoA/greek_legal_code` (CC-BY-4.0): 1,284 documents dated 1852–1999. The other 46
  volumes are out of scope.
- Models: local only, via **Ollama** (embeddings + LLM). No paid APIs.
- Storage (later): **Postgres + pgvector**. Postgres.app 16 with pgvector 0.8.6 is installed locally.
- Agent: a **LangGraph** loop: query rewriter → search tools → judge, then either loop again
  (max **3 rounds**) or answer with citations → citation check.
- Evaluation: compare **one-shot RAG** (retrieve once, answer) against **agentic RAG** (the loop above)
  on the same questions.

## Phases

- Phase list and status: README.md, section "Status". Phase 0 (data exploration) is done; findings are in
  [docs/data-exploration.md](docs/data-exploration.md). Next: Phase 1A (clean + chunk by article).
- **After each phase, update the README status, layout and diagram.**
- README style: plain, human-sounding language, short sentences, no buzzwords ("seamless", "robust",
  "leverage", "cutting-edge"), no emojis, no em-dashes.

## Working mode

- Decide small, reversible things yourself, and list them under **"Decisions I made"** at the end of
  each task.
- Ask first only for: installing packages, anything irreversible, personal data, or publishing.
- Read the installed library source instead of guessing from memory (APIs change: duckdb 2.0, for one,
  differs from 1.x).
- Git: the user commits and pushes. Claude may create commits when asked, but never pushes.
  Commits never list Claude as co-author (`.claude/settings.json` sets attribution to empty).

## Data

- Raw parquet files live in `data/raw/greek_legal_code/{volume,chapter,subject}/{train,validation,test}.parquet`.
  They hold all 47 volumes; filter to volume label 41 in code. `data/` is gitignored; never commit data.
- The 3 configs contain the same 47,563 texts in the same row order; only the label differs.
  Join them by position (the exploration script asserts this).
- Treat downloaded files as untrusted: run Python that reads them with `-I`, keep scripts outside `data/`.
- Re-run the exploration: `.venv/bin/python -I scripts/explore_data.py` (writes `data/exploration/stats.json`
  and three sample texts).

## Licences

- Our code: MIT (`LICENSE`, Copyright (c) 2026 Vyron Tempelos).
- Dataset: CC-BY-4.0, its own licence. Keep the credit in README.md.
- [TeoMastro/GreekLegislationRag](https://github.com/TeoMastro/GreekLegislationRag) (GPLv3) is
  **inspiration only**. Do not copy its code.
