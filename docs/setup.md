# Setup, commands and layout

Everything the [README](../README.md) leaves out on how to run the project: every setup step, the commands for daily use, and what each file is for.

## Setup

You need Python 3.11 (other recent versions will probably work), curl, about 11 GB of free disk space, most of it the three models,
[Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Ollama](https://ollama.com). You
don't need a local Postgres: the database runs in Docker.

Run every command below from the repository root.

1. Create the Python environment and install the packages:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Download the dataset into `data/`:

   ```bash
   base=https://huggingface.co/datasets/AI-team-UoA/greek_legal_code/resolve/main
   for c in volume chapter subject; do
     mkdir -p data/raw/greek_legal_code/$c
     for s in train validation test; do
       curl -sSL --fail -o data/raw/greek_legal_code/$c/$s.parquet "$base/$c/$s-00000-of-00001.parquet"
     done
   done
   ```

   This fetches about 440 MB. The files hold all 47 volumes and there is no smaller download for one
   volume, so the code picks out volume 41 itself.

3. Run the data exploration:

   ```bash
   .venv/bin/python -I scripts/explore_data.py
   ```

   It takes about a minute and writes `data/exploration/stats.json` plus three sample texts. It looks at
   all 47 volumes, so that the labour volume can be compared with the rest. The `-I` flag runs Python
   in isolated mode, a small precaution when reading downloaded files. This step is optional.

4. Clean and chunk the labour-law volume:

   ```bash
   .venv/bin/python -I scripts/build_chunks.py
   ```

   It takes a few seconds. It writes `data/processed/labour_chunks.jsonl` (one chunk per line),
   `data/processed/running_titles.json` (the page titles it learned to remove) and
   `docs/chunking-report.md`.

5. Start the database. First create `.env` from the template and choose a password:

   ```bash
   cp .env.example .env        # then edit POSTGRES_PASSWORD in .env
   docker compose up -d        # starts Postgres + pgvector on port 5433
   docker compose ps           # wait until the status says "healthy"
   ```

   If your shell says `docker: command not found` although Docker Desktop is running, add its command-line
   tools to your path first: `export PATH="$HOME/.docker/bin:$PATH"`.

   Other useful commands: `docker compose stop` stops the database and keeps the data;
   `docker compose down -v` deletes the database and all its data.

6. Get the embedding models and load the chunks:

   ```bash
   ollama pull bge-m3
   ollama pull qwen3-embedding:4b
   .venv/bin/python -m labour_rag.load
   .venv/bin/python -m labour_rag.embeddings
   ```

   `load` creates the tables (`sql/`), stores every chunk and embeds it with bge-m3. It shows its progress.
   Embedding the 5,740 chunks took about 5 minutes on an Apple M5. `embeddings` embeds them again with
   qwen3-embedding:4b, the model search uses by default, and that takes about 2.5 hours. You can stop it and start
   it again. Running either again is safe and takes a few seconds: they only embed chunks that are new or changed.
   To try things out without the long wait, add `--embedding bge-m3` to `ask` and `evaluate`.

7. Search:

   ```bash
   .venv/bin/python -m labour_rag.search "κανονική άδεια εργαζομένων"
   ```

   It prints the top 10 of semantic, keyword and hybrid search side by side. To measure everything again
   and rewrite `docs/search-report.md`, run `.venv/bin/python scripts/search_report.py`.

8. Ask a question:

   ```bash
   ollama pull ministral-3:8b
   .venv/bin/python -m labour_rag.ask "Πόσες ημέρες κανονική άδεια δικαιούται ο μισθωτός;"
   ```

   An answer takes about a minute. It prints the answer, its sources, the result of the citation check and the time of each step. Add
   `--show-chunks` to see exactly what the model received. The model's instructions are in
   `prompts/answer.md`. To answer the eight example questions again and rewrite `docs/answer-report.md`,
   run `.venv/bin/python scripts/answer_report.py`.

9. Run the tests:

   ```bash
   .venv/bin/python -m unittest discover -s tests -t .
   ```

10. Measure it on the test questions:

    ```bash
    .venv/bin/python -m labour_rag.evaluate --split dev
    ```

    This takes about half an hour, because the model answers 32 questions. Add `--retrieval-only` to measure search
    alone, in seconds. Results go to `eval/results/`, and a run that stops halfway continues where it left off. The 20
    questions of the test split are for one final measurement per system, so a second run by the same system is
    refused. `eval/test_runs.json` records who has used it.

## Running with Claude Haiku (optional)

Everything above works without it. **With Haiku, your question and the law chunks leave your machine** and go to Anthropic's API. The chunks are public law texts. Search, embeddings and the Query Enhancer stay local, so Docker and Ollama still have to be running.

Put your key in `.env` as `ANTHROPIC_API_KEY`. Then add `--haiku` to one question:

```bash
.venv/bin/python -m labour_rag.ask "Πόσες μέρες άδεια δικαιούμαι;" --haiku             # Haiku writes the answer
.venv/bin/python -m labour_rag.agent "Πόσες μέρες άδεια δικαιούμαι;" --haiku --trace   # Haiku is the judge and the writer
```

It says at the start what leaves your machine, and at the end what the question cost, which is usually under a cent. The key is checked before any search, at no cost. If it's missing or rejected, the command stops and says so.

These runs count in `data/haiku_manual_spend.json`, with a $2 limit. That folder is gitignored, so they don't show up as git changes. Without `--haiku`, nothing changes and nothing leaves your machine. [Models](models.md) has the details and the cost.

## Everyday commands

Once everything is set up, these are the commands you need day to day. Run them from the repository root.
If `docker` isn't found, run `export PATH="$HOME/.docker/bin:$PATH"` first.

| What | Command |
|---|---|
| Start the database | `docker compose up -d` |
| Is it running? | `docker compose ps` (look for "healthy") |
| Stop the database (keeps the data) | `docker compose stop` |
| Is Ollama running, and are the models there? | `ollama list` (needs `qwen3-embedding:4b`, `bge-m3` and `ministral-3:8b`) |
| Which models are loaded right now? | `ollama ps` |
| Load or refresh the chunks in the database | `.venv/bin/python -m labour_rag.load`, then `.venv/bin/python -m labour_rag.embeddings` |
| Search | `.venv/bin/python -m labour_rag.search "your question"` |
| Ask | `.venv/bin/python -m labour_rag.ask "your question"` (add `--show-chunks` to see the sources in full, `--fusion rrf` for the old way of searching) |
| Measure on the dev questions | `.venv/bin/python -m labour_rag.evaluate --split dev` (add `--retrieval-only` for search alone, `--fusion rrf` for another way of combining the lists) |
| Ask through the agent | `.venv/bin/python -m labour_rag.agent "your question"` (add `--trace` to see the rounds step by step) |
| Measure the agent on the dev questions | `caffeinate -i .venv/bin/python -m labour_rag.evaluate --split dev --system agent` (about an hour and a half; it continues if stopped) |
| Start the trace viewers | `docker compose --profile observability up -d` |
| Ask with a trace (with `TRACING=on` in `.env`) | `.venv/bin/python -m labour_rag.traced agent "your question" --trace` (or `ask`, or `evaluate`, and add `--haiku` as usual) |
| Stop the trace viewers | `docker compose --profile observability stop jaeger phoenix` |
| Rewrite the final report from the stored runs | `.venv/bin/python -I scripts/final_report.py` |
| Ask with Haiku (the question and chunks leave your machine) | `.venv/bin/python -m labour_rag.ask "your question" --haiku` |
| Ask through the agent with Haiku | `.venv/bin/python -m labour_rag.agent "your question" --haiku --trace` |
| Measure with Haiku on the dev questions | `.venv/bin/python -m labour_rag.evaluate --split dev --system agent-haiku` (or `oneshot-haiku`). The question and the law chunks leave your machine |
| See what the Query Enhancer makes of a question | `.venv/bin/python -m labour_rag.enhancer "your question" --search` |
| Measure the enhancer and rewrite its report | `.venv/bin/python -I scripts/enhancer_report.py --run` |
| Check the test questions against the chunks | `.venv/bin/python -I scripts/check_eval_set.py` |
| Run the tests | `.venv/bin/python -m unittest discover -s tests -t .` |

If the database or Ollama isn't running, `search` and `ask` stop with an error saying which one they can't
reach.

## Project layout

| Path | What it is for |
|---|---|
| `README.md` | What this is, the results, and how to start. |
| `CLAUDE.md` | Project notes and working rules for Claude Code. |
| `LICENSE` | MIT licence for the code in this repository. |
| `requirements.txt` | Python packages, with exact versions: duckdb (reads the dataset), psycopg (talks to Postgres), LangGraph (the agent loop), the Anthropic SDK (the optional Haiku systems) and OpenTelemetry (the optional tracing), plus everything those bring along. |
| `docker-compose.yml` | Postgres 17 with pgvector, on port 5433, and two trace viewers, Jaeger and Phoenix, that start only when asked. |
| `.env.example` | Template for `.env`: database password, ports, the Ollama model names and settings, the optional Haiku key, and the tracing switch. |
| `sql/` | The database schema, in numbered files run in order, plus the Greek stopword list `greek_labour.stop`. |
| `prompts/` | The instructions for the answering model (`answer.md`), the note every answer ends with (`closing_note.md`), and the instructions for the Query Enhancer (`enhancer.md`) and the judge (`judge.md`). |
| `docs/decisions.md` | Every architecture decision: why, the evidence and the alternatives. |
| `docs/lessons-learned.md` | The main lessons, technical and process. |
| `docs/backlog.md` | Open questions and future work, in one list. |
| `docs/setup.md` | This file. |
| `docs/data-exploration.md` | Phase 0 findings: what is in the data, its quality problems, size estimates. |
| `docs/chunking-report.md` | Phase 1A results: how the chunks were made, how many there are, real examples. |
| `docs/search-report.md` | Phase 1B results: database size, search speed, and three search methods compared on eight questions. |
| `docs/answer-report.md` | Phase 1C results: the answers to the same eight questions, their sources and citation checks, with an assessment of each. |
| `docs/eval-report.md` | Phase 2 results: what the test set contains, the numbers per experiment and category, and the most instructive failures. |
| `docs/retrieval-report.md` | Phase 3A results: five ways of combining semantic and keyword search, which one won and why, what the new refusal rule changed, and the test guard. |
| `docs/enhancer-report.md` | Phase 3B results: what the Query Enhancer adds, its outputs good and bad, and the new default embedding and repeat filter. |
| `docs/agent-report.md` | Phase 3C and 3C.1 results: the agent against one-shot, what the extra rounds did, what the two fixes changed, three traced examples and the most instructive failures. |
| `docs/final-report.md` | Phase 4A and 4B results: the five systems on dev and test side by side, claims their sources don't support, the overtime question, cost and time per run, failures by step, and how little 20 questions can show. |
| `docs/observability.md` | Tracing: what it is, how to start it, what to look at in each viewer, and which questions it answers. Its pictures are in `docs/images/`. |
| `docs/models.md` | Which model does what, where it runs and what it costs, with Haiku's settings and the budget guard. |
| `docs/how-a-question-is-answered.md` | How the final agent answers a question, for someone who doesn't read code: every rule, and one real question traced from start to finish. |
| `docs/missing-laws.md` | Laws our chunks mention but don't contain, and documents that are only a title. The fetch list for Phase 6. |
| `docs/project-journal.md` | The project owner's journal: goal, numbers, findings and lessons, phase by phase. |
| `docs/code-tour.md` | A tour of the code for people who don't read Python. |
| `eval/` | The test set (`questions.jsonl`), the owner's review of 20 items (`review.md`), the stored runs (`results/`), which system has used its one test run (`test_runs.json`), the blind readers' verdicts (`hand_read.json`) and what the measuring runs with Haiku have cost (`haiku_spend.json`). |
| `labour_rag/` | Shared Python code: cleaning and chunking (1A); settings, database, model client, loader and search (1B); choosing chunks, answering and checking citations (1C); scoring runs, matching key facts, finding law mentions and the second embedding model (2); ways of combining search results (3A); the embedding choice and the Query Enhancer (3B); the judge and the agent loop (3C). The optional Haiku client, its budget guard, the key check and the `--haiku` runs (4B). The optional tracing and its command, `traced` (5). |
| `scripts/explore_data.py` | Recomputes every number in the exploration doc. |
| `scripts/build_chunks.py` | Cleans and chunks the labour-law volume, then writes the chunks file and the chunking report. |
| `scripts/search_report.py` | Measures the database and the three search methods, then writes the search report. |
| `scripts/answer_report.py` | Answers the eight example questions and writes the answer report. |
| `scripts/check_eval_set.py` | Checks the test set against the chunks and writes the review file. |
| `scripts/eval_report.py` | Compares the stored runs and writes the evaluation report. |
| `scripts/retrieval_report.py` | Writes the retrieval report from the stored fusion runs. |
| `scripts/enhancer_report.py` | Runs the enhancer measurements and writes the enhancer report. |
| `scripts/agent_report.py` | Compares the stored agent and one-shot runs and writes the agent report. |
| `scripts/final_report.py` | Compares the five systems from their stored runs and the hand-read verdicts, and writes the final report. |
| `scripts/check_enhancer_prompt.py` | Checks that the examples in the enhancer's prompt are on topics that aren't in the test set. |
| `scripts/missing_laws.py` | Lists the laws that are mentioned but missing, and writes the fetch list. |
| `tests/` | Unit tests, using real examples from the data. |
| `.claude/settings.json` | Claude Code settings for this project. |
| `data/` | The downloaded dataset, script output, the chunks file `data/processed/labour_chunks.jsonl` and the record of manual Haiku runs. Created during setup, not in git. |
| `.venv/` | Local Python environment. Created during setup, not in git. |
| `.env` | Your local settings with the database password. Created during setup, not in git. |
