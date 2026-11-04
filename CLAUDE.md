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
  Ollama model, semantic + accent-insensitive keyword search (**done**, [docs/search-report.md](docs/search-report.md))
- 1C: one-shot baseline: search once, answer with citations, citations checked in code (**done**,
  [docs/answer-report.md](docs/answer-report.md))
- 2: evaluation set: test questions with expected answers and sources, plus retrieval and answer metrics
- 3: agentic RAG with LangGraph: rewriter (incl. katharevousa variants) → search tools → judge → max 3
  rounds → answer → citation check
- 4: compare one-shot vs agentic on the eval set (quality, time)
- 5 (later): modern layer: add Π.Δ. 80/2022 (Κώδικας Ατομικού Εργατικού Δικαίου) with a period label, so
  answers can compare historical and current law
- Backlog: extract repeal links ("Κατηργήθη δια…") into metadata. The raw sentences are already in the
  `repeal_sentences` field of each chunk.

Next: Phase 2.

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

## Database and search (Phase 1B)

- Docker CLI is not on the default PATH here: `export PATH="$HOME/.docker/bin:$PATH"` before `docker compose …`.
- `docker compose up -d` starts `labour-law-db` (pgvector/pgvector:0.8.6-pg17) on 127.0.0.1:5433, data in the
  named volume `pgdata`. Settings and password are in `.env` (gitignored); `.env.example` is the template.
- Schema = numbered files in `sql/`, each safe to re-run; `labour_rag.db.apply_schema` runs them in order. A new
  schema change gets the next number.
- After editing `sql/greek_labour.stop` (lowercase, no accents, final ς kept): `docker compose restart` (a
  single-file bind mount keeps the old file if an editor replaced it), then
  `.venv/bin/python -m labour_rag.load --rewrite`, which recomputes the stored `fts` column without re-embedding
  (a normal load leaves unchanged rows alone).
- Semantic search sets `enable_seqscan = off` around its query: vectors are TOASTed and the planner ignores that
  cost, so otherwise it never uses the HNSW index (pgvector README, "Why isn't a query using an index?").
- Load: `.venv/bin/python -m labour_rag.load` (upsert by id, embeds only new/changed chunks, deletes stale rows).
- Search: `.venv/bin/python -m labour_rag.search "…"`. Report: `.venv/bin/python scripts/search_report.py`
  (drops and rebuilds the HNSW index to measure; regenerates `docs/search-report.md`; hand-written comments live
  in its `COMMENTS` dict and must be re-checked when results change).
- All model calls go through `labour_rag/model_client.py` (Ollama HTTP API via urllib); model names come from `.env`.
- Installed Python packages: duckdb, psycopg[binary]. Ask before adding more.

## Answering (Phase 1C)

- `.venv/bin/python -m labour_rag.ask "…" [--show-chunks]`: `retrieve.py` (hybrid top 30 → skip near-duplicates
  at 50% word overlap and a 3rd chunk per document → 8 chunks) → one `chat()` call → `citations.check`.
- Chat settings in `.env`: CHAT_MODEL (ministral-3:8b), CHAT_TEMPERATURE 0.2, CHAT_NUM_CTX 16384, CHAT_SEED 42.
  `chat()` raises if the prompt fills the context window (Ollama would cut it silently).
- Model instructions: `prompts/answer.md` (`{closing_note}` is filled from `prompts/closing_note.md`). The user edits
  these; don't move rules into code. The code appends the closing note if the model leaves it out.
- Citation check: [n] must exist; «quotes» need a citation in the same sentence and must appear in that chunk
  (accent/case-insensitive, "…" may skip words); failures show the closest passage and its similarity.
- Report: `.venv/bin/python scripts/answer_report.py` (asks the model, stores `data/processed/answer_results.json`);
  `--rewrite-only` rewrites `docs/answer-report.md` from stored results. The hand-written verdicts live in its
  `ASSESSMENTS`, `OVERALL` and `LIMIT_NOTE` and must be redone whenever the answers are regenerated.

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
