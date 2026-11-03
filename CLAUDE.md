# labour-law-greek-rag

Learning project: **agentic RAG over Greek labour law**, fully local.

## Goal

- Scope: **labour law only**, i.e. volume 41 (label id 41, *ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ*) of the Hugging Face
  dataset `AI-team-UoA/greek_legal_code` (CC-BY-4.0): 1,284 documents dated 1852–1999. The other 46
  volumes are out of scope. Later (Phase 5) a modern layer adds Π.Δ. 80/2022, labelled by period.
- Models: local only, via **Ollama** (embeddings + LLM). No paid APIs.
- Storage: **Postgres + pgvector in Docker on port 5433**. Postgres.app already runs on 5432; leave it alone.
- Search: semantic (vectors) plus accent-insensitive keyword search.
- Agent: a **LangGraph** loop: rewriter (incl. katharevousa variants) → search tools → judge → max
  **3 rounds** → answer → citation check.
- Evaluation: an eval set (questions with expected answers and sources), then **one-shot RAG** vs
  **agentic RAG** on it, for quality and time.

## Phases

Same list as README.md "Status"; keep the two in sync.

- 0: explore the data (**done**, [docs/data-exploration.md](docs/data-exploration.md))
- 1A: clean and chunk (**done**, [docs/chunking-report.md](docs/chunking-report.md), output
  `data/processed/labour_chunks.jsonl`; non-programmer tour in [docs/code-tour.md](docs/code-tour.md))
- 1B: Postgres + pgvector in Docker (port 5433, because Postgres.app uses 5432), embeddings with a local
  Ollama model, semantic + accent-insensitive keyword search
- 1C: one-shot baseline: search once, answer with citations, citations checked in code
- 2: evaluation set: test questions with expected answers and sources, plus retrieval and answer metrics
- 3: agentic RAG with LangGraph: rewriter (incl. katharevousa variants) → search tools → judge → max 3
  rounds → answer → citation check
- 4: compare one-shot vs agentic on the eval set (quality, time)
- 5 (later): modern layer: add Π.Δ. 80/2022 (Κώδικας Ατομικού Εργατικού Δικαίου) with a period label, so
  answers can compare historical and current law
- Backlog: extract repeal links ("Κατηργήθη δια…") into metadata. The raw sentences are already in the
  `repeal_sentences` field of each chunk.

Next: Phase 1B.

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
