# labour-law-greek-rag

## What this is

A learning project that answers questions about Greek labour law from 1852-1999. It uses agentic RAG:
it searches 1,284 laws, decrees and decisions, rewrites the question and searches again when the
results are weak, and answers with citations. Everything runs locally with Ollama, with no paid APIs.

## Status

- [x] Phase 0: Explore the data. Findings are in [docs/data-exploration.md](docs/data-exploration.md).
- [x] Phase 1A: Clean the labour-law texts and split them into chunks. Results are in [docs/chunking-report.md](docs/chunking-report.md).
- [x] Phase 1B: Postgres + pgvector in Docker (port 5433, because Postgres.app already uses 5432), embeddings with a local Ollama model, and both semantic and accent-insensitive keyword search. Results are in [docs/search-report.md](docs/search-report.md).
- [x] Phase 1C: One-shot baseline: search once, answer with citations, and check the citations in code. Results are in [docs/answer-report.md](docs/answer-report.md): none of the eight answers is fully right yet (four partly, four wrong), so the later phases have a clear baseline to beat.
- [x] Phase 2: Evaluation set: 52 test questions with expected answers and sources, plus retrieval and answer metrics. Results are in [docs/eval-report.md](docs/eval-report.md): on the test questions, the right text reached the model for 12 of 17, and 7 of 16 answers had every key fact. Later phases have to beat that. Laws our data mentions but doesn't contain are listed in [docs/missing-laws.md](docs/missing-laws.md).
- [x] Phase 3A: Fix the step that combines semantic and keyword search. Results are in [docs/retrieval-report.md](docs/retrieval-report.md): semantic search alone won, and the right text now reaches the model for 17 of 27 dev questions instead of 13. No answers were written in this step.
- [ ] Phase 3: Agentic RAG with LangGraph: rewriter (including katharevousa variants) → search tools → judge → at most 3 rounds → answer → citation check.
- [ ] Phase 4: Compare one-shot and agentic RAG on the evaluation set, for answer quality and time.
- [ ] Phase 5 (later): Add a modern layer with Π.Δ. 80/2022 (Κώδικας Ατομικού Εργατικού Δικαίου), labelled by period, so answers can compare historical and current law.

Backlog: extract the repeal links ("Κατηργήθη δια…") into metadata.

## How it works

The index, the search, the one-shot answer with its citation check and the measuring are built. The
rewriter and the judge are the plan. Keyword search is built too, but since Phase 3A answers use semantic
search alone by default, because mixing the two lost more than it found. `--fusion rrf` brings back the old way.

```
BUILD THE INDEX (once)

  greek_legal_code, volume 41
        |
        v
  explore the data ................ built     Phase 0
        |
        v
  clean, chunk by article ......... built     Phase 1A
        |
        v
  embed with Ollama,
  store in Postgres + pgvector .... built     Phase 1B


ANSWER A QUESTION

  question
        |
        v
  rewriter ........................ planned   Phase 3  <-----+
        |                                                    |
        v                                                    |
  search tools .................... built     Phase 1B, 3A   |
        |                                                    |
        v                                                    |
  judge: enough to answer? ........ planned   Phase 3        |
        |   no, and fewer than 3 rounds done: try again -----+
        |   yes, or 3 rounds done
        v
  answer with citations ........... built     Phase 1C
        |
        v
  citation check .................. built     Phase 1C


MEASURE IT

  52 test questions with expected answers and sources
        |
        v
  run search and answer,
  count what came out right ....... built     Phase 2
        |
        v
  compare one-shot and agentic .... planned   Phase 4
```

The one-shot baseline from Phase 1C skips the rewriter and the judge. It searches once and answers.
Phase 2 measured it on the test questions, and Phase 4 compares the two versions on the same questions.

## Project layout

| Path | What it is for |
|---|---|
| `README.md` | This file. |
| `CLAUDE.md` | Project notes and working rules for Claude Code. |
| `LICENSE` | MIT licence for the code in this repository. |
| `requirements.txt` | Python packages: duckdb (reads the dataset) and psycopg (talks to Postgres). |
| `docker-compose.yml` | Postgres 17 with pgvector, on port 5433. |
| `.env.example` | Template for `.env`: database password, ports, and the Ollama model names and settings. |
| `sql/` | The database schema, in numbered files run in order, plus the Greek stopword list `greek_labour.stop`. |
| `prompts/` | The instructions for the answering model (`answer.md`) and the note every answer ends with (`closing_note.md`). Edit them freely. |
| `docs/data-exploration.md` | Phase 0 findings: what is in the data, its quality problems, size estimates. |
| `docs/chunking-report.md` | Phase 1A results: how the chunks were made, how many there are, real examples. |
| `docs/search-report.md` | Phase 1B results: database size, search speed, and three search methods compared on eight questions. |
| `docs/answer-report.md` | Phase 1C results: the answers to the same eight questions, their sources and citation checks, with an assessment of each. |
| `docs/eval-report.md` | Phase 2 results: what the test set contains, the numbers per experiment and category, and the most instructive failures. |
| `docs/retrieval-report.md` | Phase 3A results: five ways of combining semantic and keyword search, which one won and why, what the new refusal rule changed, and the test guard. |
| `docs/missing-laws.md` | Laws our chunks mention but don't contain, and documents that are only a title. The fetch list for Phase 5. |
| `docs/project-journal.md` | The project owner's journal: goal, numbers, findings and lessons, phase by phase. |
| `docs/code-tour.md` | A tour of the code for people who don't read Python. |
| `eval/` | The test set (`questions.jsonl`), the owner's review of 20 items (`review.md`), the stored runs (`results/`) and which system has used its one test run (`test_runs.json`). |
| `labour_rag/` | Shared Python code: cleaning and chunking (1A); settings, database, model client, loader and search (1B); choosing chunks, answering and checking citations (1C); scoring runs, matching key facts, finding law mentions and the second embedding model (2); ways of combining search results (3A). |
| `scripts/explore_data.py` | Recomputes every number in the exploration doc. |
| `scripts/build_chunks.py` | Cleans and chunks the labour-law volume, then writes the chunks file and the chunking report. |
| `scripts/search_report.py` | Measures the database and the three search methods, then writes the search report. |
| `scripts/answer_report.py` | Answers the eight example questions and writes the answer report. |
| `scripts/check_eval_set.py` | Checks the test set against the chunks and writes the review file. |
| `scripts/eval_report.py` | Compares the stored runs and writes the evaluation report. |
| `scripts/retrieval_report.py` | Runs the fusion experiments and writes the retrieval report. |
| `scripts/missing_laws.py` | Lists the laws that are mentioned but missing, and writes the fetch list. |
| `tests/` | Unit tests, using real examples from the data. |
| `.claude/settings.json` | Claude Code settings for this project. |
| `data/` | The downloaded dataset, script output and the chunks file `data/processed/labour_chunks.jsonl`. Created during setup, not in git. |
| `.venv/` | Local Python environment. Created during setup, not in git. |
| `.env` | Your local settings with the database password. Created during setup, not in git. |

## Setup and running

You need Python 3.11 (other recent versions will probably work), curl, about 2 GB of free disk space,
[Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Ollama](https://ollama.com). You
don't need a local Postgres: the database runs in Docker.

Run every command below from the repository root, the folder that contains this README.

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

   This fetches about 460 MB. The files hold all 47 volumes and there is no smaller download for one
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

6. Get the embedding model and load the chunks:

   ```bash
   ollama pull bge-m3
   .venv/bin/python -m labour_rag.load
   ```

   This creates the tables (`sql/`), stores every chunk and embeds it with bge-m3. It shows its progress.
   Embedding the 5,740 chunks took about 5 minutes on an Apple M5. Running it again is safe and takes a few
   seconds: it only embeds chunks that are new or changed.

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

## Everyday commands

Once everything is set up, these are the commands you need day to day. Run them from the repository root.
If `docker` isn't found, run `export PATH="$HOME/.docker/bin:$PATH"` first.

| What | Command |
|---|---|
| Start the database | `docker compose up -d` |
| Is it running? | `docker compose ps` (look for "healthy") |
| Stop the database (keeps the data) | `docker compose stop` |
| Is Ollama running, and are the models there? | `ollama list` (needs `bge-m3` and `ministral-3:8b`) |
| Which models are loaded right now? | `ollama ps` |
| Load or refresh the chunks in the database | `.venv/bin/python -m labour_rag.load` |
| Search | `.venv/bin/python -m labour_rag.search "your question"` |
| Ask | `.venv/bin/python -m labour_rag.ask "your question"` (add `--show-chunks` to see the sources in full, `--fusion rrf` for the old way of searching) |
| Measure on the dev questions | `.venv/bin/python -m labour_rag.evaluate --split dev` (add `--retrieval-only` for search alone, `--fusion rrf` for another way of combining the lists) |
| Compare the ways of combining search results | `.venv/bin/python -I scripts/retrieval_report.py --run` |
| Compare a second embedding model (optional) | `ollama pull qwen3-embedding:4b`, then `.venv/bin/python -m labour_rag.embed_experiment` (about 2.5 hours), then the line above with `--retrieval-only --embedding qwen3-4b` |
| Check the test questions against the chunks | `.venv/bin/python -I scripts/check_eval_set.py` |
| Run the tests | `.venv/bin/python -m unittest discover -s tests -t .` |

If the database or Ollama isn't running, `search` and `ask` stop with an error saying which one they can't
reach.

## Data and credits

**Dataset.** The law texts come from the Greek Legal Code (GLC) dataset,
[AI-team-UoA/greek_legal_code](https://huggingface.co/datasets/AI-team-UoA/greek_legal_code) on Hugging
Face. Papaloukas et al. built it from the "Permanent Greek Legislation Code - Raptarchis" catalogue.
The dataset keeps its own licence, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The MIT
licence in this repository covers only the code. The data is not copied into this repository: you
download it yourself in step 2. Any cleaning or chunking we do changes the original text, and that is
documented in `docs/`.

> Christos Papaloukas, Ilias Chalkidis, Konstantinos Athinaios, Despina-Athanasia Pantazi and Manolis
> Koubarakis. *Multi-granular Legal Topic Classification on Greek Legislation.* Proceedings of the
> Natural Legal Language Processing Workshop 2021. <https://arxiv.org/abs/2109.15298>

**Inspiration.** [TeoMastro/GreekLegislationRag](https://github.com/TeoMastro/GreekLegislationRag)
(GPLv3) gave us the idea. No code was copied from it.

**Please read this.** The law texts stop in 1999. Greek labour law has changed a lot since then, and many
of these acts were later amended or repealed. This is a learning project. It is not legal advice, and its
answers should not be used for decisions about a real job or employment dispute.

## Known limitations

Details and numbers are in [docs/data-exploration.md](docs/data-exploration.md).

- **Old law only.** The newest labour text is from 1999.
- **Many documents are thin.** Only 445 of the 1,284 labour documents are divided into articles. Many
  of the rest are a header and a short note, such as "this act was repealed".
- **Laws are missing.** The chunks mention 700 laws and decrees that aren't documents in our data, among
  them Ν. 435/1976 on overtime pay, and 468 documents hold only a title. The list is in
  [docs/missing-laws.md](docs/missing-laws.md).
- **Messy text.** It was converted from the Word files of a printed collection. There are no line
  breaks, page headers sit in the middle of sentences, and articles are sometimes out of order.
- **Look-alike characters.** Some Greek words contain Latin letters (`τoυ` with a Latin `o`), and some
  texts use the micro sign `µ` instead of the Greek `μ`. These have to be fixed before searching.
- **Old and new Greek mixed.** Katharevousa and demotic appear side by side, and accents are often
  missing, so keyword search has to ignore accents.
- **Volume 41 only.** Related rules in other volumes are left out, for example seafarers' contracts
  (merchant shipping), unemployment benefits (social insurance) and civil servants. The main decree on
  safety at building sites (Π.Δ. 1073/1981) is also in another volume.
- **Everyday words versus legal words.** Search can miss a law that uses different words from the
  question: "οικοδομές" doesn't find the act on "εργοτάξια". Some acts are only a header without their
  text. Near-identical clauses (from ILO conventions, or decisions repeated every year) can fill a result
  list. Details are in [docs/search-report.md](docs/search-report.md).
- **The repeat filter can hide a newer law.** It ignores numbers, so a rule of 16 weeks and an older rule of 15
  weeks can count as repeats, and only the one ranked first reaches the model. See
  [docs/retrieval-report.md](docs/retrieval-report.md).
