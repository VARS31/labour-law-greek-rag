# laborlaw-greek-rag

A learning project: agentic retrieval-augmented generation (RAG) over Greek legislation, starting with
labour law. Everything runs locally: models via Ollama, and later Postgres + pgvector for search, with a
LangGraph agent that rewrites the question, searches, judges the results and retries (up to 3 rounds).
The plan is to compare it against plain one-shot RAG.

**Status:** Phase 0, data exploration. See [docs/data-exploration.md](docs/data-exploration.md).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Download the dataset (~460 MB of parquet files) into data/ (gitignored)
base=https://huggingface.co/datasets/AI-team-UoA/greek_legal_code/resolve/main
for c in volume chapter subject; do
  mkdir -p data/raw/greek_legal_code/$c
  for s in train validation test; do
    curl -sSL --fail -o data/raw/greek_legal_code/$c/$s.parquet "$base/$c/$s-00000-of-00001.parquet"
  done
done

# Reproduce the numbers in docs/data-exploration.md
.venv/bin/python -I scripts/explore_data.py
```

## Data and credits

This project uses the **Greek Legal Code (GLC)** dataset,
[`AI-team-UoA/greek_legal_code`](https://huggingface.co/datasets/AI-team-UoA/greek_legal_code) on
Hugging Face, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It was created
by Papaloukas et al. from the "Permanent Greek Legislation Code - Raptarchis" catalogue. The data is not
redistributed here: it is downloaded locally into `data/`. Any cleaning or chunking we do is a change to
the original and will be documented in `docs/`.

> Christos Papaloukas, Ilias Chalkidis, Konstantinos Athinaios, Despina-Athanasia Pantazi and Manolis
> Koubarakis. *Multi-granular Legal Topic Classification on Greek Legislation.* Proceedings of the
> Natural Legal Language Processing Workshop 2021. <https://arxiv.org/abs/2109.15298>

## Inspiration

[TeoMastro/GreekLegislationRag](https://github.com/TeoMastro/GreekLegislationRag) (GPLv3) inspired the
idea. This repository does not copy any of its code.
