# laborlaw-greek-rag

Learning project: **agentic RAG over Greek legal text**, fully local.

## Goal

- Corpus: Greek legislation from the Hugging Face dataset `AI-team-UoA/greek_legal_code` (CC-BY-4.0),
  starting with the labour-law volume (ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ).
- Models: local only, via **Ollama** (embeddings + LLM). No paid APIs.
- Storage (later): **Postgres + pgvector**.
- Agent: a **LangGraph** loop: query rewriter → search tools → judge, then either answer or loop again
  (max **3 rounds**).
- Evaluation: compare **one-shot RAG** (retrieve once, answer) against **agentic RAG** (the loop above)
  on the same questions.

## Phases

- **Phase 0 (current): explore the data only.** No embeddings, no database yet.
  Findings: [docs/data-exploration.md](docs/data-exploration.md).

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
  `data/` is gitignored; never commit data.
- The 3 configs contain the same 47,563 texts in the same row order; only the label differs.
  Join them by position (the exploration script asserts this).
- Treat downloaded files as untrusted: run Python that reads them with `-I`, keep scripts outside `data/`.
- Re-run the exploration: `.venv/bin/python -I scripts/explore_data.py` (writes `data/exploration/stats.json`
  and three sample texts).

## Licences

- Dataset: CC-BY-4.0 — keep the credit in README.md.
- [TeoMastro/GreekLegislationRag](https://github.com/TeoMastro/GreekLegislationRag) (GPLv3) is
  **inspiration only**. Do not copy its code.
