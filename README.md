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
- [x] Phase 3B: The Query Enhancer: one model call that rewrites a question into searches in the words of the law. Results are in [docs/enhancer-report.md](docs/enhancer-report.md): it adds no right chunks, 22 of 27 dev questions with or without it, and takes about 7 seconds. This step also made qwen3-embedding:4b the default and stopped the repeat filter from hiding newer rules.
- [x] Phase 3C: The agent loop with LangGraph: search → judge → search again if asked, at most 3 rounds → answer → citation check. Results are in [docs/agent-report.md](docs/agent-report.md): on the dev questions, 15 of 26 answers are complete against 12 for one-shot, at about 167 seconds against 63. The judge's filter brings the gain. The extra rounds rescued no answer.
- [x] Phase 3C.1: Two fixes: searching stops once an approved chunk answers directly, and round 2 reads further down the plain question's list. Results are in [docs/agent-report.md](docs/agent-report.md): one real rescue (`single-09`), wrong refusals down from 2 to 1, no new complete answer, and no faster. The agent is now frozen for Phase 4. [docs/how-a-question-is-answered.md](docs/how-a-question-is-answered.md) gives every rule in plain words and traces one question.
- [ ] Phase 4: Compare one-shot and agentic RAG on the evaluation set, for answer quality and time.
- [ ] Phase 5 (later): Add a modern layer with Π.Δ. 80/2022 (Κώδικας Ατομικού Εργατικού Δικαίου), labelled by period, so answers can compare historical and current law.

Backlog: extract the repeal links ("Κατηργήθη δια…") into metadata.

## How it works

All of it is built. There are two ways to answer: one-shot (`labour_rag.ask`), which searches once and answers, and
the agent (`labour_rag.agent`), which is the diagram below. The agent searches the plain question first and uses the
rewriter only when the judge asks for another try, because Phase 3B showed the rewriter adds little as a first step. Since
Phase 3A answers use semantic search alone by default, because mixing it with keyword search lost more than it
found (`--fusion rrf` brings back the old way). Since Phase 3B search uses qwen3-embedding:4b (`--embedding bge-m3`
brings back the old model). To follow one question from start to finish, with every rule and a real example, read
[docs/how-a-question-is-answered.md](docs/how-a-question-is-answered.md).

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
  store in Postgres + pgvector .... built     Phase 1B, 3B


ANSWER A QUESTION

  question
        |
        v
  search the plain question ....... built     Phase 1B, 3A
        |
        v
  judge: which chunks fit,  ....... built     Phase 3C <------------+
  and what next?                                                    |
        |   search again, at most 3 rounds in all:                  |
        |     further down the list (round 2 only),                 |
        |     rewriter, laws it named, next articles .. built  3B, 3C
        |   refuse: the code says so, and names the law if known
        |   answer: go on, also if the judge wants more but
        |     an approved chunk answers directly ...... built  3C.1
        v
  answer from approved chunks,
  with citations .................. built     Phase 1C, 3C
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

The one-shot baseline from Phase 1C skips the judge. It searches once and answers.
Phase 2 measured it on the test questions, and Phase 4 compares the two versions on the same questions.

## Project layout

| Path | What it is for |
|---|---|
| `README.md` | This file. |
| `CLAUDE.md` | Project notes and working rules for Claude Code. |
| `LICENSE` | MIT licence for the code in this repository. |
| `requirements.txt` | Python packages, with exact versions: duckdb (reads the dataset), psycopg (talks to Postgres) and LangGraph (the agent loop), plus everything LangGraph brings along. |
| `docker-compose.yml` | Postgres 17 with pgvector, on port 5433. |
| `.env.example` | Template for `.env`: database password, ports, and the Ollama model names and settings. |
| `sql/` | The database schema, in numbered files run in order, plus the Greek stopword list `greek_labour.stop`. |
| `prompts/` | The instructions for the answering model (`answer.md`), the note every answer ends with (`closing_note.md`), and the instructions for the Query Enhancer (`enhancer.md`) and the judge (`judge.md`). Edit them freely. |
| `docs/data-exploration.md` | Phase 0 findings: what is in the data, its quality problems, size estimates. |
| `docs/chunking-report.md` | Phase 1A results: how the chunks were made, how many there are, real examples. |
| `docs/search-report.md` | Phase 1B results: database size, search speed, and three search methods compared on eight questions. |
| `docs/answer-report.md` | Phase 1C results: the answers to the same eight questions, their sources and citation checks, with an assessment of each. |
| `docs/eval-report.md` | Phase 2 results: what the test set contains, the numbers per experiment and category, and the most instructive failures. |
| `docs/retrieval-report.md` | Phase 3A results: five ways of combining semantic and keyword search, which one won and why, what the new refusal rule changed, and the test guard. |
| `docs/enhancer-report.md` | Phase 3B results: what the Query Enhancer adds, its outputs good and bad, and the new default embedding and repeat filter. |
| `docs/agent-report.md` | Phase 3C and 3C.1 results: the agent against one-shot, what the extra rounds did, what the two fixes changed, three traced examples and the most instructive failures. |
| `docs/how-a-question-is-answered.md` | How the final agent answers a question, for someone who doesn't read code: every rule, and one real question traced from start to finish. |
| `docs/missing-laws.md` | Laws our chunks mention but don't contain, and documents that are only a title. The fetch list for Phase 5. |
| `docs/project-journal.md` | The project owner's journal: goal, numbers, findings and lessons, phase by phase. |
| `docs/code-tour.md` | A tour of the code for people who don't read Python. |
| `eval/` | The test set (`questions.jsonl`), the owner's review of 20 items (`review.md`), the stored runs (`results/`) and which system has used its one test run (`test_runs.json`). |
| `labour_rag/` | Shared Python code: cleaning and chunking (1A); settings, database, model client, loader and search (1B); choosing chunks, answering and checking citations (1C); scoring runs, matching key facts, finding law mentions and the second embedding model (2); ways of combining search results (3A); the embedding choice and the Query Enhancer (3B); the judge and the agent loop (3C). |
| `scripts/explore_data.py` | Recomputes every number in the exploration doc. |
| `scripts/build_chunks.py` | Cleans and chunks the labour-law volume, then writes the chunks file and the chunking report. |
| `scripts/search_report.py` | Measures the database and the three search methods, then writes the search report. |
| `scripts/answer_report.py` | Answers the eight example questions and writes the answer report. |
| `scripts/check_eval_set.py` | Checks the test set against the chunks and writes the review file. |
| `scripts/eval_report.py` | Compares the stored runs and writes the evaluation report. |
| `scripts/retrieval_report.py` | Writes the retrieval report from the stored fusion runs. |
| `scripts/enhancer_report.py` | Runs the enhancer measurements and writes the enhancer report. |
| `scripts/agent_report.py` | Compares the stored agent and one-shot runs and writes the agent report. |
| `scripts/check_enhancer_prompt.py` | Checks that the examples in the enhancer's prompt are on topics that aren't in the test set. |
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
| See what the Query Enhancer makes of a question | `.venv/bin/python -m labour_rag.enhancer "your question" --search` |
| Measure the enhancer and rewrite its report | `.venv/bin/python -I scripts/enhancer_report.py --run` |
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
- **Old and new rules can reach the model together.** Chunks that state different numbers are never treated as
  repeats, so a question on maternity leave can get 14, 15 and 16 weeks at once. Nothing yet tells the model to
  prefer the newest. See [docs/enhancer-report.md](docs/enhancer-report.md).
- **The Query Enhancer's katharevousa is often not real Greek,** and it can't find a word of the law it doesn't
  know. Only the agent's second try uses it.
- **The agent is slow, and the judge can be wrong.** A question takes about 3 minutes, most of it the judge. It can
  reject the right chunk or call a wrong one relevant, and that can end the search. The writer can still misread a
  chunk it was given, or add something no chunk says. See [docs/agent-report.md](docs/agent-report.md).
