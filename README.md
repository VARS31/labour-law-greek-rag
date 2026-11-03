# labour-law-greek-rag

## What this is

A learning project that answers questions about Greek labour law from 1852-1999. It uses agentic RAG:
it searches 1,284 laws, decrees and decisions, rewrites the question and searches again when the
results are weak, and answers with citations. Everything runs locally with Ollama, with no paid APIs.

## Status

- [x] Phase 0: Explore the data. Findings are in [docs/data-exploration.md](docs/data-exploration.md).
- [x] Phase 1A: Clean the labour-law texts and split them into chunks, one per article. Results are in [docs/chunking-report.md](docs/chunking-report.md).
- [ ] Phase 1B: Embed the chunks with a local Ollama model and store them in Postgres + pgvector.
- [ ] Phase 1C: One-shot RAG baseline: search once, then answer with citations.
- [ ] Phase 2: Agent loop in LangGraph: rewriter, search tools and judge, at most 3 rounds.
- [ ] Phase 3: Citation check: confirm that each cited article says what the answer claims.
- [ ] Phase 4: Evaluation: one-shot RAG against agentic RAG on the same set of questions.

## How it works

The data exploration and the cleaning and chunking are built. The rest is the plan.

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
  store in Postgres + pgvector .... planned   Phase 1B


ANSWER A QUESTION

  question
        |
        v
  rewriter ........................ planned   Phase 2   <-----+
        |                                                    |
        v                                                    |
  search tools .................... planned   Phase 1C       |
        |                                                    |
        v                                                    |
  judge: enough to answer? ........ planned   Phase 2        |
        |   no, and fewer than 3 rounds done: try again -----+
        |   yes, or 3 rounds done
        v
  answer with citations ........... planned   Phase 1C
        |
        v
  citation check .................. planned   Phase 3
```

The one-shot baseline from Phase 1C skips the rewriter and the judge. It searches once and answers.
Phase 4 compares the two versions.

## Project layout

| Path | What it is for |
|---|---|
| `README.md` | This file. |
| `CLAUDE.md` | Project notes and working rules for Claude Code. |
| `LICENSE` | MIT licence for the code in this repository. |
| `requirements.txt` | Python packages. Only duckdb for now. |
| `docs/data-exploration.md` | Phase 0 findings: what is in the data, its quality problems, size estimates. |
| `docs/chunking-report.md` | Phase 1A results: how the chunks were made, how many there are, real examples. |
| `labour_rag/` | Shared Python code: text normalisation, page-noise removal, header parsing, article detection, chunking. |
| `scripts/explore_data.py` | Recomputes every number in the exploration doc. |
| `scripts/build_chunks.py` | Cleans and chunks the labour-law volume, then writes the chunks file and the chunking report. |
| `tests/` | Unit tests, using real examples from the data. |
| `.claude/settings.json` | Claude Code settings for this project. |
| `data/` | The downloaded dataset, script output and the chunks file `data/processed/labour_chunks.jsonl`. Created during setup, not in git. |
| `.venv/` | Local Python environment. Created during setup, not in git. |

## Setup and running

You need Python 3.11 (other recent versions will probably work), curl and about 500 MB of free disk
space. Ollama and Postgres are not needed yet.

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

5. Run the tests:

   ```bash
   .venv/bin/python -m unittest discover -s tests -t .
   ```

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
- **Messy text.** It was converted from the Word files of a printed collection. There are no line
  breaks, page headers sit in the middle of sentences, and articles are sometimes out of order.
- **Look-alike characters.** Some Greek words contain Latin letters (`τoυ` with a Latin `o`), and some
  texts use the micro sign `µ` instead of the Greek `μ`. These have to be fixed before searching.
- **Old and new Greek mixed.** Katharevousa and demotic appear side by side, and accents are often
  missing, so keyword search has to ignore accents.
- **Volume 41 only.** Related rules in other volumes are left out, for example seafarers' contracts
  (merchant shipping), unemployment benefits (social insurance) and civil servants.
