# Models

Which model does what, where it runs and what it costs. The project is local by default. Haiku is optional, and chosen per run.

| Model | Used for | Where it runs | Cost |
|---|---|---|---|
| `qwen3-embedding:4b` | Search: turns chunks and questions into vectors. The default since Phase 3B. | Local, Ollama | No money |
| `bge-m3` | The earlier embeddings. The Phase 2 baseline and the Phase 1 reports use it. | Local, Ollama | No money |
| `ministral-3:8b` | Judge and Writer on the local systems. The Query Enhancer on every system. | Local, Ollama | No money |
| `claude-haiku-5-5` | Judge and Writer on `oneshot-haiku` and `agent-haiku`. | Cloud, Anthropic's API | See below |

## Claude Haiku

**What it's for.** It replaces the local model as the Writer on `oneshot-haiku`, and as the Judge and the Writer on `agent-haiku`. Search, embeddings and the Query Enhancer stay local on every system, and the prompts are the same ones the local model uses.

**What leaves your machine.** With Haiku, your question and the law chunks go to Anthropic's API. The chunks are public law texts. Nothing leaves your machine on the local systems.

**Price.** $0.10 per million input tokens and $0.50 per million output tokens, for prompts up to 100,000 tokens. Longer prompts cost $0.50 and $2.50, and ours never come close. Checked on Anthropic's [pricing page](https://platform.claude.com/docs/en/about-claude/pricing) on 2026-11-05. Its thinking counts as output, and it's most of the output here.

**What it really cost,** counted after every call:

| Run | Questions | Calls | Tokens in | Tokens out | Cost | Time for the run |
|---|---:|---:|---:|---:|---:|---:|
| `oneshot-haiku`, dev | 32 | 32 | 312,522 | 87,645 | $0.0751 | 6.2 min |
| `agent-haiku`, dev | 32 | 64 | 558,725 | 147,855 | $0.1298 | 11.4 min |
| `oneshot-haiku`, test | 20 | 20 | 197,853 | 47,873 | $0.0437 | 3.5 min |
| `agent-haiku`, test | 20 | 44 | 413,650 | 100,863 | $0.0918 | 8.0 min |

With a tiny key check and two trial questions, all of Phase 4B came to $0.35. The running total is in [`eval/haiku_spend.json`](../eval/haiku_spend.json). That covers the calls to Haiku, not the work of reading the answers.

**Settings.** No temperature and no seed, because the API takes neither. Thinking stays at the model's default effort. Output is capped at 16,000 tokens, which leaves room for the thinking; a call that reaches the cap stops the run. No caching. Nothing was tuned, so its runs aren't exactly repeatable, and it isn't "only the model that changes".

**How to use it.** Put `ANTHROPIC_API_KEY` in `.env`, which git ignores. Then:

```bash
.venv/bin/python -m labour_rag.haiku_client                              # is the key set, and does it work? one tiny call
.venv/bin/python -m labour_rag.evaluate --split dev --system agent-haiku  # or oneshot-haiku
```

The key is read only to hand to the SDK. It's never printed, logged or stored. `labour_rag.ask` and `labour_rag.agent` stay local: only measuring runs use Haiku.

**The budget guard.** [`labour_rag/budget.py`](../labour_rag/budget.py) stops at $1 per run and $3 across all of Phase 4B. It counts real usage after every call and keeps the total on disk, so a resumed run still counts what it spent before. It doesn't make a call that could pass a limit, and a stopped run can continue. The workspace has its own $10 monthly limit, set in Anthropic's Console.

**What it does well and badly.** On the test questions, 10 of 16 answers are complete on both Haiku systems, against 5 and 4 on the local ones, and its complete answers say less that their sources don't support. It still doesn't tell υπερεργασία from υπερωρία. The figures, and how little 20 questions can show, are in [the final report](final-report.md).
