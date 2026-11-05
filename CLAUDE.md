# labour-law-greek-rag

Learning project: **agentic RAG over Greek labour law**, fully local.

## Goal

- Scope: **labour law only**, i.e. volume 41 (label id 41, *ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ*) of the Hugging Face
  dataset `AI-team-UoA/greek_legal_code` (CC-BY-4.0): 1,284 documents dated 1852–1999. The other 46
  volumes are out of scope. Later (Phase 5) a modern layer adds Π.Δ. 80/2022, labelled by period.
- Models: local only, via **Ollama** (embeddings + LLM). No paid APIs.
- Storage: **Postgres + pgvector in Docker on port 5433**. Postgres.app already runs on 5432; leave it alone.
- Search: semantic (vectors) plus accent-insensitive keyword search.
- Agent: a **LangGraph** loop: search → judge → search again (rewriter with katharevousa variants) → max
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
- 2: evaluation set: test questions with expected answers and sources, plus retrieval and answer metrics (**done**,
  [docs/eval-report.md](docs/eval-report.md); fetch list for Phase 5 in [docs/missing-laws.md](docs/missing-laws.md))
- 3A: fix the fusion step: five ways of combining the search lists compared, retrieval only (**done**,
  [docs/retrieval-report.md](docs/retrieval-report.md))
- 3B: the Query Enhancer and multi-query search, retrieval only; qwen3 as the default embedding; repeat filter fixed (**done**,
  [docs/enhancer-report.md](docs/enhancer-report.md))
- 3C: agentic RAG with LangGraph: search → judge → search again, max 3 rounds → answer → citation check (**done**,
  [docs/agent-report.md](docs/agent-report.md))
- 4: compare one-shot vs agentic on the eval set (quality, time)
- 5 (later): modern layer: add Π.Δ. 80/2022 (Κώδικας Ατομικού Εργατικού Δικαίου) with a period label, so
  answers can compare historical and current law
- Backlog: extract repeal links ("Κατηργήθη δια…") into metadata. The raw sentences are already in the
  `repeal_sentences` field of each chunk.

Next: Phase 4.

- **After each phase, update the README status, layout and diagram.**
- At the end of each phase, append a compact block to docs/project-journal.md: goal, what was done, key numbers, findings, decisions, lessons. Keep the existing text.
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
- Load: `.venv/bin/python -m labour_rag.load` (upsert by id, embeds only new/changed chunks with bge-m3, deletes stale rows), then
  `.venv/bin/python -m labour_rag.embeddings` for the qwen3 vectors of new or changed chunks.
- Embeddings: `labour_rag/embeddings.py` holds the registry and `DEFAULT_EMBEDDING` (`qwen3-4b`: `qwen3-embedding:4b` with its query
  instruction, table `chunk_embeddings_qwen3_4b`, about 2.5 hours for all chunks). `bge-m3` stays selectable with `--embedding`, its
  vectors in the `chunks` table. EMBED_MODEL in `.env` is only for those: `labour_rag.load` needs it to fit `vector(1024)`, so don't
  put qwen3 there. `scripts/search_report.py` and `scripts/answer_report.py` pin bge-m3.
- Search: `.venv/bin/python -m labour_rag.search "…"`. Report: `.venv/bin/python scripts/search_report.py`
  (drops and rebuilds the HNSW index to measure; regenerates `docs/search-report.md`; hand-written comments live
  in its `COMMENTS` dict and must be re-checked when results change).
- All model calls go through `labour_rag/model_client.py` (Ollama HTTP API via urllib); model names come from `.env`, except qwen3's
  in `labour_rag/embeddings.py`.
- Installed Python packages: duckdb, psycopg[binary], langgraph and what it brings (37 packages, all pinned in `requirements.txt`). Ask before adding more.

## Answering (Phase 1C)

- `.venv/bin/python -m labour_rag.ask "…" [--show-chunks] [--fusion rrf] [--embedding bge-m3]`: `retrieve.py` (top 30, by default from
  semantic search alone → skip repeats and a 3rd chunk per document → 8 chunks) → one `chat()` call → `citations.check`.
  `search.hybrid` stays equal-weight RRF, and `scripts/answer_report.py` pins `fusion="rrf"` and bge-m3, so the Phase 1B and 1C reports
  describe what they measured.
- Repeats (`retrieve.select`): 50% word overlap and the same `rule_numbers`, meaning numbers with a unit (`16 εβδομάδες`, `10%`, `27.012
  δρχ`). Article numbers, decision numbers, dates and ΦΕΚ don't count, or a decision re-issued every year would never be a repeat.
  Among repeats the newest act takes the older one's place. `number_rule="digits"` is the literal "every digit" reading (`--number-rule digits`).
- Chat settings in `.env`: CHAT_MODEL (ministral-3:8b), CHAT_TEMPERATURE 0.2, CHAT_NUM_CTX 16384, CHAT_SEED 42.
  `chat()` raises if the prompt fills the context window (Ollama would cut it silently).
- Model instructions: `prompts/answer.md` (`{closing_note}` is filled from `prompts/closing_note.md`). The user edits
  these; don't move rules into code. The code appends the closing note if the model leaves it out.
- Citation check: [n] must exist; «quotes» need a citation in the same sentence and must appear in that chunk
  (accent/case-insensitive, "…" may skip words); failures show the closest passage and its similarity.
- Report: `.venv/bin/python scripts/answer_report.py` (asks the model, stores `data/processed/answer_results.json`);
  `--rewrite-only` rewrites `docs/answer-report.md` from stored results. The hand-written verdicts live in its
  `ASSESSMENTS`, `OVERALL` and `LIMIT_NOTE` and must be redone whenever the answers are regenerated.

## Evaluation (Phase 2)

- `.venv/bin/python -m labour_rag.evaluate --split dev [--fusion rrf] [--max-per-document 4] [--retrieval-only] [--embedding bge-m3|qwen3-4b-plain] [--number-rule digits] [--enhancer variants|with-question] [--reuse-enhancer <dir>]`
  writes `eval/results/<date>_<config>/` (items.jsonl, summary.json, summary.md) and continues if interrupted.
  `--rescore <dir>` checks and scores stored answers again without a model or database (chunk text comes from the chunks file).
- Test split: one run per named system, recorded in `eval/test_runs.json` (`claim_test_run`). The one-shot baseline has used its
  run (`2026-11-04_oneshot-limit2-test`, equal-weight RRF). `evaluate` refuses `--system agent --split test`: the agent's one run belongs to Phase 4, so
  ask the owner first. Don't tune on the test split and don't read its answers: report which test items change by id only. A fresh test
  needs new questions.
- Refusals: `citations.is_refusal`, the prompt's "Δεν βρέθηκε" or other clear words near the start of the answer, unless the
  sentence goes on with "αλλά". It doesn't check that a refusal names where the rule would be.
- Test set: `eval/questions.jsonl`. Expected answers follow our data, not today's law. After editing it, run
  `.venv/bin/python -I scripts/check_eval_set.py` (about a minute): every quote must be in its chunk. Its `--write-review`
  never overwrites `eval/review.md`, which holds the owner's verdicts.
- Key facts are matched in `labour_rag/key_facts.py`, without a model. It was tuned once on dev answers.
- Report: `.venv/bin/python -I scripts/eval_report.py` rewrites `docs/eval-report.md` from the stored runs. The hand-written
  `OVERALL`, `COMMENT_B`, `COMMENT_C`, `TEST_COMMENT`, `FAILURES`, `NEXT` and `HAND_FACTS` must be redone when the runs change.
- Fetch list: `.venv/bin/python -I scripts/missing_laws.py` rewrites `docs/missing-laws.md`; never edit it by hand.
- Fusion experiments (Phase 3A): `.venv/bin/python -I scripts/retrieval_report.py` rewrites `docs/retrieval-report.md` from the stored
  runs. It works out the winner and stops if that isn't `search.DEFAULT_FUSION`. Those runs used the old repeat filter, so they can't be
  repeated with today's code (commit 79de467 has the code). Run names before Phase 3B have no number rule in them.
- Don't run two Ollama jobs at once while measuring time. A model run's times also move with the machine's load.

## Query Enhancer (Phase 3B)

- `labour_rag/enhancer.py`: one `chat()` call at temperature 0 with a JSON schema. `.venv/bin/python -m labour_rag.enhancer "…" [--search]`.
  Instructions in `prompts/enhancer.md`; the user edits it. The code drops a law reference or a search phrase with a number the question
  doesn't contain, because the schema fixes only the shape.
- The prompt's examples must be on topics outside `eval/questions.jsonl`: `.venv/bin/python -I scripts/check_enhancer_prompt.py`, also run by
  `tests/test_enhancer.py`. Keep each example on two lines, `Ερώτηση: …` and `JSON: {…}`, so the check can read it.
- Multi-query search: `search.multi_query`, ranked by `best_similarity` (each chunk keeps its highest similarity to any one search). With
  `law_refs`, keyword search may add up to 2 chunks after the first 6.
- It added no right chunks as a first step on dev and takes about 7 s, so only the agent's round 2 and 3 use it. `evaluate --enhancer` measures it alone and
  needs `--retrieval-only`.
- Report: `.venv/bin/python -I scripts/enhancer_report.py [--run]`. Hand-written `RESULT`, `MISSES`, `EXAMPLES`, `LIMITS` and text in `main`; the
  script stops if the claims it checks stop holding. Editing the prompt means re-running the enhancer: `--reuse-enhancer` only re-reads stored answers.

## Agent (Phase 3C)

- `labour_rag/agent.py` is the LangGraph graph: `.venv/bin/python -m labour_rag.agent "…" [--trace]`. Its nodes close over the connection and the client. It switches LangSmith tracing
  off before importing LangGraph; keep that first.
- `labour_rag/judge.py`: one `chat()` call at temperature 0 with a JSON schema; the last round's schema can't say `search_again`. Instructions in `prompts/judge.md`; the user edits it, and its
  example must stay off the test set (`tests/test_agent.py` checks). Approved means relevant or partly, doesn't fail to apply, and isn't replaced by a really newer approved act.
- The code, not the model, writes refusals and says when a law isn't in our data (`law_in_data`). A law the Judge names must be cited in the chunks (`named_laws`): matching digits aren't enough,
  because "Β.Δ. 16/18 Ιουλ. 1920" is a date. Telling someone a law is missing when it isn't is the worst mistake here.
- Evaluate: `.venv/bin/python -m labour_rag.evaluate --split dev --system agent`, about an hour and a half. `agent_problem` labels failures search, judge or writer. Start long runs with `caffeinate -i`; a run
  started from Claude's session stops when the session does, and continues if started again the same day.
- Report: `.venv/bin/python -I scripts/agent_report.py`. Hand-written `RESULT`, `ROUNDS`, `FAILURES`, `NEXT`, `LIMITS` and `WRONG_THOUGH_COMPLETE`, from reading the answers; the script stops if the claims it checks stop holding.

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
