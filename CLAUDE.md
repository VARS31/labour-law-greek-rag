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

- Phase list and status: README.md, section "Status". Done: Phase 0 (data exploration,
  [docs/data-exploration.md](docs/data-exploration.md)) and Phase 1A (cleaning + chunking,
  [docs/chunking-report.md](docs/chunking-report.md), output `data/processed/labour_chunks.jsonl`).
  Next: Phase 1B (embed with Ollama, store in Postgres + pgvector).
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
- Build the chunks: `.venv/bin/python -I scripts/build_chunks.py` (writes `data/processed/labour_chunks.jsonl`,
  `data/processed/running_titles.json` and regenerates `docs/chunking-report.md`; never edit the report by hand).
- Tests: `.venv/bin/python -m unittest discover -s tests -t .` (stdlib unittest; pytest is not installed).

## Code

- Shared code lives in `labour_rag/`. Scripts in `scripts/` add the repo root to `sys.path` themselves,
  because `-I` leaves it out.
- Clean user questions with `labour_rag.normalize.normalize`, the same function used on the corpus.
- `labour_rag/articles.py` is the maintained article regex. `scripts/explore_data.py` keeps the older
  Phase 0 copy so the Phase 0 numbers stay reproducible.

## Licences

- Our code: MIT (`LICENSE`, Copyright (c) 2026 Vyron Tempelos).
- Dataset: CC-BY-4.0, its own licence. Keep the credit in README.md.
- [TeoMastro/GreekLegislationRag](https://github.com/TeoMastro/GreekLegislationRag) (GPLv3) is
  **inspiration only**. Do not copy its code.
