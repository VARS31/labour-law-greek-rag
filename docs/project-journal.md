# Project journal: labour-law-greek-rag

Where we are, what each phase found, and what we decided. Compact on purpose: one block per phase. Add a block after every phase.

---

## Where we are now

```
Phase 0   Explore the data ............................. done
Phase 1A  Clean + chunk ................................ done
Phase 1B  Database (Docker) + embeddings + search ...... done
Phase 1C  One-shot answers (baseline) .................. done   0 of 8 fully correct
Phase 2   Test set + measurements ...................... done   test: 7 of 16 answers complete
Phase 3A  Fix the fusion step (retrieval only) ......... done   dev: right chunk 17 of 27, was 13
Phase 3   Agentic RAG with LangGraph
Phase 4   Comparisons (one-shot vs agent, models, maybe Claude Haiku)
Phase 5   Modern layer (Π.Δ. 80/2022 + missing laws)
```

**The system in one picture**

```
BUILD THE LIBRARY (once)
  Hugging Face parquet → build_chunks (clean + cut) → labour_chunks.jsonl → load (bge-m3 → numbers) → Postgres in Docker

ANSWER A QUESTION (every time)
  question → clean → search (semantic / keyword / hybrid) → top chunks → writer (ministral) → citation check
  later:  Query Enhancer → search → Judge (max 3 rounds) → Writer → citation check
```

**Who does what**

| Part | Tool | AI? |
|---|---|---|
| Text → numbers (chunks once, each question) | bge-m3 via Ollama | yes, numbers only |
| Find nearest chunks | Postgres + pgvector | no, maths |
| Write the answer | ministral-3:8b via Ollama | yes |
| Database | Postgres 17 + pgvector in Docker, port 5433 | no |

---

## Phase 0: explore the data

**Goal:** understand the Hugging Face dataset before designing anything.

**Findings**
- 47,563 Greek legal documents, 1821–2009, sorted into 47 volumes → 389 chapters → 2,285 subjects.
- Labour law = volume 41: 1,284 documents, stops in **1999**.
- Typical document is tiny (median 79 words): often just a title or a "repealed" note.
- Messy text: µ instead of μ, Latin letters inside Greek words, broken accents, printed page headers inside sentences, no line breaks, shuffled article order.
- Size: labour law ≈ 5,300 chunks ≈ 90 MB (fits anywhere); full dataset ≈ 3.2 GB.

**Decisions:** labour law only; local Postgres in Docker; MIT licence for my code, dataset stays CC-BY-4.0.

**Lesson:** look at real data before designing. The dataset was built for **topic classification**, not for complete legal texts. That explains many gaps later.

---

## Phase 1A: clean and chunk

**Goal:** turn 1,284 messy documents into clean, self-explaining chunks. No AI.

**What we did:** normalisation (characters) → noise removal (page headers) → structure-aware chunking (by article, fallback: numbered paragraph, then size) → metadata (law, number, year, ΦΕΚ, article) → contextual header in front of each chunk → flags (stub, note, repeal sentence) → generated report + tests.

**Numbers:** 5,740 chunks, median 81 words. 445 documents split by article, 140 by paragraph, 13 by size, 686 kept whole.

**Lessons**
- Chunk quality is the ceiling for everything after it.
- Old books print an article's title *before* its marker; cutting at the marker glued titles to the wrong article (1,222 moved).
- Every chunk must carry its "address" (law + article), or neither search nor the writer knows where it comes from.

---

## Phase 1B: database, embeddings, search

**Goal:** store chunks with vectors in Postgres (Docker) and search three ways.

**Numbers:** embedding 5,740 chunks took 5.2 minutes. Database 112 MB. Search: 15 ms without index, 1.6 ms with HNSW, same results.

**Findings**
- Semantic search best on 5 of 8 questions; hybrid put the main law at #1 in 7 of 8.
- Keyword search is fooled by ambiguous words ("αποζημίωση" also means travel allowance).
- **One word decides success:** "οικοδομές" never finds Π.Δ. 305/1996, "εργοτάξια" finds it at #1 → the Query Enhancer's job.
- Near-duplicates (ILO conventions, yearly bonus decisions) crowd the top 10.

**Docker learned:** image = the software (frozen, from the internet); container = it running; **volume = where my data lives**; docker-compose.yml = the recipe. Data updates never need a new image.

---

## Phase 1C: one-shot answers (baseline)

**Goal:** search once, answer once, check citations in code. The baseline for later comparisons.

**Result:** 0 of 8 fully correct (4 partly, 4 wrong). About 30–70 seconds per answer.

**Failure types**

| Type | Example | Fix belongs to |
|---|---|---|
| Search problem: right text not retrieved | dismissal notice periods outside the top 50 | Query Enhancer, Judge (search again), better embedding model |
| Reading problem: right text there, misused | ΚΤΕΛ overtime rule sold as the general rule | Judge (filter / label chunks), stronger Writer |
| No refusal | building sites answered from a decree that excludes them | Judge decides "enough or refuse" |
| Invented quotes | only 40% of quotes found in their chunk | citation check catches, doesn't prevent |
| A setting | 2-per-document limit threw away real answers | test limit 4 |

**Key lessons**
- **A confident, well-formatted answer can be wrong.** Test C (overtime) looked correct but mixed the ΚΤΕΛ rule into Ν.Δ. 515/1970; the general rule (Ν. 435/1976) isn't even in the data.
- **"Citation check passed" ≠ "answer correct".** It proves words exist, not that the reasoning is right.
- **Diagnostic question for every failure:** was the answer in the chunks the model received? No → search problem. Yes → reading problem.
- Refusals work for clearly unknown things (Ν. 4808/2021, the word "question").

---

## Phase 2: test set (in progress)

**Goal:** ~50 questions with written-down correct answers and sources, so every change gets a number instead of a feeling.

**Done so far:** 52 items drafted (32 dev, 20 test) in 6 categories: single source, sector traps, vocabulary mismatch, follow-a-reference, must-refuse, exact lookup. A checker confirmed every gold quote exists in its chunk and no question copies the law's wording. 20 items reviewed by me.

**Findings while building it: the dataset has real gaps**
- Key laws are **missing** entirely, only mentioned: Ν. 435/1976 (overtime rates), Ν. 2556/1997 (20-year leave), Ν. 1483/1984, Ν.Δ. 4020/1959, Ν. 1545/1985.
- Some laws are **title only**: Π.Δ. 305/1996 (building sites).
- Older and newer rules disagree inside the data (maternity leave 14 vs 16 weeks; working week 48 vs 40 hours). Expected answer = the newer one.
- Some rules surprise today's reader (night baking banned 21:30–06:00 in the 1954/1981 rule): that's historical law.

**Decisions:** answers follow **our data**, not today's law; questions use everyday words; dev/test split (never tune on test); "not answerable" items count as correct when the answer says "not found" and names where the rule would be.

**Next:** metrics script → baseline numbers → experiments (per-document limit 4; bge-m3 vs qwen3-embedding) → eval report. Plus a "missing laws" inventory for Phase 5.

---

## Phase 2: measurements (done)

**Goal:** measure the one-shot baseline on the test set, so later phases have numbers to beat.

**What we did:** metrics script with results stored per run in `eval/results/` → key facts matched without a model (agrees with a hand check on 68 of 71) → dev baseline → limit 4 → bge-m3 vs qwen3-embedding, retrieval only → one test run → [eval-report.md](eval-report.md). Plus the fetch list for Phase 5: [missing-laws.md](missing-laws.md).

**Numbers**

| | Dev, limit 2 | Dev, limit 4 | Test, limit 2 (run once) |
|---|---|---|---|
| Right chunk among the 8 | 13 of 27 | 16 of 27 | 12 of 17 |
| Right chunk in the top 50 | 24 of 27 | 24 of 27 | 17 of 17 |
| Answers with every key fact | 9 of 26 | 7 of 26 | 7 of 16 |
| Citation check passed | 10 of 26 | 14 of 26 | 7 of 16 |
| Correct refusals | 4 of 6 | 4 of 6 | 2 of 4 |
| Wrong refusals | 1 of 26 | 1 of 26 | 1 of 16 |
| Search / reading problems | 13 / 6 | 10 / 11 | 5 / 6 |
| Median time per question | 36 s | 45 s | 54 s |

| Embedding model (dev) | bge-m3 | qwen3-embedding:4b |
|---|---|---|
| Semantic alone: right chunk in its top 8 | 20 of 27 | 23 of 27 |
| Hybrid: right chunk among the 8 | 13 of 27 | 14 of 27 |
| Embedding all chunks | 5 minutes | about 2.5 hours |

Missing laws: 2,716 mentions point to 700 laws we don't have, 274 of them in other volumes of the dataset. 468 documents are only a title.

**Findings**
- **Hybrid search is the weak link.** Semantic alone has the right chunk in its top 8 for 20 of 27; only 13 reach the model. Fusion buries what keyword search can't find (`vocab-06`: first in semantic, 14th in hybrid).
- Vocabulary mismatches: 0 of 4 on dev got the right chunk among the 8.
- A better embedding model barely helps while fusion stays as it is (one more question).
- Limit 4 delivers more right chunks but the answers don't improve. One extra chunk can change an answer (`sector-03`).
- The citation check doesn't predict quality: 4 of 10 passing answers were complete, against 5 of 16 failing ones.
- The model can invent things that aren't quotes, so the check can't see them ("κατώτατο μισθό του 2024" from sources that stop in 1999).

**Decisions:** final baseline = hybrid, bge-m3, limit 2. Test answers stay unread. qwen3 vectors stay in their own table; the choice of model waits until fusion is fixed. Phase 3 starts with fusion, because a retrieval-only run takes seconds.

**Lessons**
- Measure each step on its own. The final answers alone would never have shown that the chunk was found and then lost.
- Before buying a better model, check where the result gets lost.
- With 27 questions, one question is about 4 points. Differences of a question or two are noise.
- A score matched without a model can't read meaning: it can't see "δεν". Check it by hand once, and say how far it can be trusted.

---

## Phase 3A: fix the fusion step

**Goal:** stop losing the right chunk when the semantic and keyword lists are combined. Retrieval only, on dev: no writer, no prompt changes.

**What we did:** five ways of combining the lists × bge-m3 and qwen3 × limit 2 and 4 → winner picked by the rule (most right chunks reaching the writer; within one question, the simpler way) → made it the default, old way selectable with `--fusion rrf` → wider refusal detection, all stored answers scored again → test split now runs once per named system → [retrieval-report.md](retrieval-report.md).

**Numbers** (questions of 27 whose right chunk reaches the writer)

| Way of combining | bge-m3, limit 2 | bge-m3, limit 4 | qwen3, limit 2 | qwen3, limit 4 |
|---|---|---|---|---|
| (a) RRF, equal weights (old) | 13 | 16 | 14 | 17 |
| (b) RRF, semantic counts double | 15 | 17 | 19 | 20 |
| **(c) Semantic only (winner)** | **17** | 19 | 22 | 23 |
| (d) Semantic, keyword only if a law is named | 17 | 19 | 22 | 23 |
| (e) 6 semantic places, then 2 keyword | 17 | 20 | 22 | 23 |

qwen3 beats bge-m3 by 5 of 27 at limit 2 and 4 at limit 4, so it clears the bar of 3. The default stays bge-m3 until I decide.

Refusals: 2 past results change, both to wrong refusals: `lookup-01` (dev, wrong refusals 1 → 2, citation check 10 → 11 of 26) and `lookup-02` (test, wrong refusals 1 → 2). The Phase 2 block above keeps the old numbers.

**Findings**
- **Why fusion failed:** with constant 60 and 50 chunks per list, any chunk in both lists beat the first result of either list, even at 50th in each.
- Of the five questions fusion had lost, 4 now arrive (`vocab-06`, `reference-01`, `single-14`, `vocab-02`). `single-17` is now stopped by the limit of 2, not by fusion.
- Keyword search added nothing at limit 2. But dev has only 2 questions with a gold chunk that name a law, and `sector-02` is 2nd in keyword and 20th in semantic.
- **The repeat filter can hide a newer law:** it ignores numbers, so 15 weeks (older) and 16 weeks (newer) count as repeats and `single-15` now gets the older one. Not fixed yet.

**Decisions:** semantic only is the new default. Limit stays 2. Test baseline stays the old setup, because one-shot has used its one run. The agent gets its own run in Phase 4.

**Lessons**
- Work the formula out by hand. Two lines of arithmetic explained the failure the numbers had only shown.
- A filter that was harmless under one order can do damage under another. Changing one step can expose another.
- The simplest option can win. A rule fixed in advance (within one question, the simpler way) stops me talking myself into something fancier.
- More right chunks is a promise, not a result. Only a run with the writer can show better answers.

---

## Open questions and ideas (backlog)

- Missing-laws inventory → fetch exactly those from official ΦΕΚ in Phase 5.
- Extract repeal links ("Κατηργήθη δια…") into metadata.
- Group near-duplicates in search results.
- Phase 4: compare local writer/judge with Claude Haiku (estimated ~$0.30 per full agent test run; workspace spend limit + budget guard in code).
- Same architecture for other countries' law: only the ingestion (cleaning, chunking rules, stopwords, prompts, test set) is source-specific.

---

## Glossary (my words)

| Term | Meaning |
|---|---|
| Chunk | One piece of a law (usually one article) stored as one row |
| Embedding / vector | A text's meaning as ~1,000 numbers |
| Semantic search | Find chunks with the closest meaning |
| Keyword search | Find chunks with the same words (accent-insensitive) |
| Hybrid / RRF | Combine both rankings; a chunk high in both wins |
| HNSW index | Speed-up structure for vector search; approximate |
| Baseline | The simple version we measure improvements against |
| Recall@8 | Share of questions where a correct chunk is among the 8 the model receives |
| Gold source | The chunk that really contains the correct answer |
| Dev / test split | Dev: allowed to look at while improving. Test: only for final measurement |
| Query Enhancer | Agent that rewrites the question before searching |
| Judge | Agent that checks retrieved chunks: relevant? enough? search again? |
| Writer | Model that writes the final answer from approved chunks |
