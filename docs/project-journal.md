# Project journal: labour-law-greek-rag

Where we are, what each phase found, and what we decided. Compact on purpose: one block per phase. Add a block after every phase.

---

## Where we are now

```
Phase 0   Explore the data ............................. done
Phase 1A  Clean + chunk ................................ done
Phase 1B  Database (Docker) + embeddings + search ...... done
Phase 1C  One-shot answers (baseline) .................. done   0 of 8 fully correct
Phase 2   Test set + measurements ...................... done   test: 7 of 16 answers complete (5 when read)
Phase 3A  Fix the fusion step (retrieval only) ......... done   dev: right chunk 17 of 27, was 13
Phase 3B  Query Enhancer (retrieval only) .............. done   dev: no gain, 22 of 27 with or without it
Phase 3C  Agent loop with LangGraph .................... done   dev: 12 of 26 complete vs 9 (corrected in 4A and 4B), 167 s vs 63 s
Phase 3C.1 Two fixes, then frozen ...................... done   dev: 1 real rescue, wrong refusals 2 → 1, still 12 of 26
Phase 3   Agentic RAG with LangGraph .................. done (3A, 3B, 3C)
Phase 4A  Final test runs, three systems side by side .. done   test: agent 4 of 16 complete vs 5 and 5, too few to separate them
Phase 4B  Claude Haiku as Judge and Writer, budget guard . done   test: 10 of 16 complete on both, vs 5 and 4 local, $0.35 in all
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

## Phase 3B: the Query Enhancer

**Goal:** turn a person's question into searches in the words of the law, and see if more right chunks reach the writer. Retrieval only, on dev. Housekeeping first: qwen3 as the default embedding, and a repeat filter that can't hide a newer rule.

**What we did:** made qwen3 the default, bge-m3 selectable → repeat filter: different numbers are never repeats, newest act wins among real repeats → one call to ministral-3:8b at temperature 0, JSON answer, instructions in `prompts/enhancer.md` → code drops any law or phrase with a number the question doesn't contain → search each phrasing, each chunk keeps its best similarity → measured against 3A's default → [enhancer-report.md](enhancer-report.md).

**Numbers** (qwen3, semantic, limit 2, 27 questions)

| | Without the enhancer | Phrasings alone | Phrasings + the question |
|---|---|---|---|
| Right chunk reaches the writer | 22 | 21 | 22 (the same questions) |
| Right chunk in the top 50 | 27 | 25 | 27 |
| MRR | 0.61 | 0.57 | 0.63 |
| Time per question | 0.1 s | 7.5 s | 7.6 s |

Repeat filter: `single-15` on bge-m3 arrives again (17 → 18). On qwen3 no right chunk changes, but the 8 chunks change for 10 questions. Read literally ("every digit"), the rule would remove 6 repeats instead of 45 and hand the writer 28 near-identical pairs instead of 8, so the filter counts numbers with a unit. To check: is that reading right?

**Findings**
- **The enhancer adds no right chunks.** qwen3 with semantic search had already solved 3 of the 4 vocabulary questions. The fourth needs "εργοτάξια", and the model never says it.
- **The small model's katharevousa is often not real Greek:** "μισθώδεια", "μεροκαιρομισθούντων", "υπερπερισσότερον". The embeddings forgive a lot of it.
- **A JSON schema fixes the shape, not the truth.** `law_refs` was clean, but a phrasing named Ν.Δ. 146/1979, which nobody asked about. The rewrite also turned "εργάτης σε εργοστάσιο" into "μισθωτός σε επιχείρηση", the one detail that decides `sector-01`.
- It does reach different chunks: `sector-05` arrives only through the phrasings, and `lookup-03` is saved by the keyword places.
- Keeping all the rules means the writer can get 14, 15 and 16 weeks at once. Choosing the newest is now a job for the judge.

**Decisions:** qwen3 is the default (my decision after 3A). Numbers with a unit count for repeats; every digit stays selectable. The enhancer stays out of answering for now. The agent should pass the person's own question along with the phrasings.

**Open:** run the enhancer first on every question, as planned, or only as the agent's second try when the judge says no? The numbers point to the second try.

**Lessons**
- A negative result is a result. This looked like the obvious fix for vocabulary problems, and a better embedding and simpler search had already done most of it.
- Read a rule against real data before applying it. Many digits in a chunk only name the act, so "different numbers" had to mean numbers that state something.
- Check what the model produces in every field, not only the one you worry about.

---

## Phase 3C: the agent loop

**Goal:** join search, Judge and writer into an agent with LangGraph, and measure it with full answers against the one-shot.

**What we did:** LangGraph 1.2.20 installed, 37 packages pinned, tracing off → Judge in `prompts/judge.md`: a verdict per chunk, then answer, search again or refuse → round 2 uses the enhancer, laws the Judge named and next articles → writer sees only approved chunks and my original question → refusals and "law not in our data" written by the code → `--trace` → full dev run → [agent-report.md](agent-report.md).

**Numbers** (32 dev questions; 26 answerable, 6 to refuse)

| | One-shot (qwen3, semantic, limit 2) | Agent |
|---|---|---|
| Key facts found | 68% | 76% |
| Every key fact, by matching | 12 | 16 |
| Every key fact, checked by hand | 12 | 15 |
| Correct refusals | 4 of 6 | 5 of 6 |
| Wrong refusals | 0 | 2 |
| Writer saw the right chunk | 22 of 27 | 22 of 27 (not the same ones) |
| Rounds | 1 | 23 took 1, 5 took 2, 4 took 3 |
| Median time per question | 63 s | 167 s |

Failures: search 3, Judge 2, writer 7. The Judge takes 67 of the 91 minutes.

**Findings**
- **The Judge's filter brings the gain, not the extra rounds.** The writer reads 3.4 chunks instead of 8. It rejects rules for other groups, and on `single-15` it kept 16 weeks and dropped 14 and 15.
- **Round 2 rescued nothing on dev.** The right chunk arrives in round 1 or never. Of 9 questions that searched again, 1 got better, 2 got worse, 6 changed nothing. 22 minutes spent.
- **The Judge can undo itself.** `vocab-03`: approved the right chunk in round 1, rejected it in round 2.
- **The score hid a wrong answer.** `sector-01` counts as complete, but it tells a worker with six years "5 days" where the rule says 30. The writer is now the biggest source of failures.
- A false claim caught in the trial: the Judge named the decree it was reading, and the code said "its text isn't in our data". Fixed. All 11 such claims in the full run are true.
- `lookup-02` on test: my verdict is a real refusal, so the new rule is right, and a wrong refusal caused by search (right chunk at rank 16).

**Decisions:** plain search first, enhancer only on the second try. Writer sees my original question, never the rewrite. Code writes refusals. The agent's test run waits for Phase 4.

**Open:** stop when a right chunk is in hand (3 of 9 went on anyway)? Let round 2 read further down the plain list (`single-09` at rank 15, `vocab-01` at rank 19)? That's the likeliest real rescue, and it's untested.

**Lessons**
- Read the answers. A score that can't read meaning hid a wrong answer in the headline number.
- More rounds aren't more help by themselves. Each round is another chance to change a right decision.
- Long runs need `caffeinate`, and a run started from a session dies with the session. Save each result as it finishes, so stopping costs nothing.

---

## Phase 3C.1: two fixes, then freeze

**Goal:** make the two fixes Phase 3C pointed to, measure them once on dev, freeze the agent for Phase 4, and write down exactly how a question is answered.

**What we did:** stop rule: if the Judge asks to search again but an approved chunk is relevant and applies, the code writes instead → round 2 also reads the next 8 places on the plain list → one dev re-run → read every answer that changed → comparison in [agent-report.md](agent-report.md) → agent frozen at the local tag `agent-frozen-3c1` → [how-a-question-is-answered.md](how-a-question-is-answered.md), with `single-09` traced end to end.

**Key numbers (dev, 3C → 3C.1):**

| Measure | 3C | 3C.1 |
|---|---:|---:|
| Key facts | 76% | 78% |
| Complete, checked by hand | 15 of 26 | 15 of 26 |
| Correct refusals | 5 of 6 | 5 of 6 |
| Wrong refusals | 2 | 1 |
| Writer saw the right chunk | 22 of 27 | 24 of 27 |
| Citation check passed | 15 of 26 | 13 of 26 |
| Questions with 1 / 2 / 3 rounds | 23 / 5 / 4 | 26 / 4 / 2 |
| Judge tokens | 347,386 | 312,808 |
| Measured time | 91 min | 94 min |

**Findings**
- **The first real rescue.** `single-09`: right chunk at rank 15, read in round 2, approved, and the stop rule ended the search. It had been a wrong refusal.
- **It isn't a clean rescue.** The main rule is right, but the writer adds that a change without a document is void, citing chunks that don't say that. The citation check can't see it.
- **No new complete answer, and no key fact lost.** 26 of 32 answers are word for word the same. One question of 27 shows the fix can work, not how often.
- **The stop rule believes the Judge.** It fired 5 times, and only 2 were on a chunk that really answers. On `refuse-06` the Judge called an article on penalties relevant to child custody, and only the writer's own refusal saved it.
- `vocab-03` didn't improve. The right chunk now stays with the writer, which answers from another one. The failure moved from the Judge to the writer.
- **It isn't measurably faster.** 5 fewer rounds and 10% fewer Judge tokens, but round 2 now reads 4 more chunks each time.

**Decisions:** numbers with a unit stays the repeat rule (my decision). Both fixes stay. The agent is frozen: `labour_rag/` except `evaluate.py`, `prompts/`, `sql/` and the `CHAT_*` settings. Any later change is a new named system with its own run.

**Lessons**
- Check a timing claim before believing it. Two refusals took twice as long, so I was told the machine was slower. The 23 questions with exactly the same work took 53 and 51 minutes: the speed only moved around within each run. Tokens are the fair measure.
- Write the rules down and check them against the code. A line-by-line check of the walkthrough found 3 false statements, and a fresh read with only the code found 13 more mistakes: 6 false, 7 too strong. They all sounded right.
- A fix that works on the question it was aimed at can act on the Judge's mistakes elsewhere. Read all the places it fired, not only the one it was for.

---

## Phase 4A: final test runs

**Goal:** run the two systems that still had a test run, set all three side by side on dev and test, and say honestly how little 20 questions can show.

**What we did:** test guard lifted for exactly `oneshot-v2` and `agent`, with their settings pinned and the freeze check in code → both run detached on 2026-11-05, one after the other → every test answer scored complete read blind by two readers → every dev answer scored complete re-read by one rule → [final-report.md](final-report.md) → Results section in the README.

**Key numbers:**

| Measure | Dev: baseline | Dev: v2 | Dev: agent | Test: baseline | Test: v2 | Test: agent |
|---|---:|---:|---:|---:|---:|---:|
| Complete, read by hand | 6 of 26 | 9 of 26 | 13 of 26 | 5 of 16 | 5 of 16 | 4 of 16 |
| Key facts | 51% | 68% | 78% | 60% | 69% | 66% |
| Correct refusals | 4 of 6 | 4 of 6 | 5 of 6 | 2 of 4 | 1 of 4 | 3 of 4 |
| Wrong refusals | 2 | 0 | 1 | 2 | 1 | 2 |
| Right chunk reached the Writer | 13 of 27 | 22 of 27 | 24 of 27 | 12 of 17 | 15 of 17 | 14 of 17 |
| Median time | 36 s | 63 s | 141 s | 54 s | 49 s | 118 s |
| Failures: search / Judge / Writer | 13 / - / 9 | 4 / - / 15 | 2 / 1 / 11 | 5 / - / 8 | 1 / - / 13 | 0 / 3 / 10 |

**Findings**
- **The agent's lead on dev didn't carry over.** 13 against 9 and 6 on dev, 4 against 5 and 5 on test. A gap of one answer shows neither that it's better nor that it's worse. It shows the dev lead can't be taken at face value: its rules were built on those answers.
- **Refusing is where the agent leads on both sets.** 3 of 4 on test against 1 and 2. Its two wrong refusals on test are the Judge's, with the right chunk in places 1 and 2.
- **Better search alone didn't give better answers.** The right chunk reaches the Writer for 15 of 17 on v2 against 12 on the baseline, and complete answers stay at 5.
- **The Writer is now the weak step.** 10 of the agent's 13 failures on test, and 13 of v2's 14 (3 of those are questions it should have refused, with no Judge to catch them). Some may be the matcher's misses: test answers scored incomplete weren't read.
- **Complete doesn't mean right in every sentence.** 12 of the 14 test answers that pass say something else their source doesn't support. Only key facts count, so these stay as passes, but anyone relying on an answer should check the source.
- **The order on test depends on close calls.** One verdict either way gives 6, 5, 4, and stricter readings of three others give 3, 4, 4.
- **Correction:** Phase 3C said 15 complete answers against 12 on dev. Reading both systems by one rule gives 13 against 9. The 3C and 3C.1 blocks above keep the old number as written, and [agent-report.md](agent-report.md) is corrected.

**Decisions:** the Phase 2 baseline keeps its Phase 2 run. An answer fails if it states a key fact wrong or leaves one out, anywhere, short answer included, for all systems; other mistakes are noted, not counted. The second reader's verdict on the baseline's `single-08` stands, and the report says it came after the labels were open. The agent stays frozen at `agent-frozen-3c1`.

**Lessons**
- A lead on the questions you built with isn't evidence. Keep a test set back, and expect it to disappoint.
- Read every system by the same rule. Checking only the new one made my first number wrong.
- A blind second reader is cheap. It agreed on 17 of 18, and the one difference was a mistake of mine: I compared the answer with the chunk and not with the words of the key fact.
- Size the test set before comparing systems. With 16 answerable questions, one close call can reorder the table.

---

## Phase 4B: Haiku as Judge and Writer

**Goal:** see what a better model changes, with the agent's logic and the prompts untouched. Local by default, cloud optional, chosen per run. Two new systems: `oneshot-haiku` (Writer) and `agent-haiku` (Judge and Writer). Search, embeddings and the Query Enhancer stay local.

**What we did:** installed the official SDK (4 new packages, pinned) → a client with the same `chat()` as the local one, and no frozen file changed → budget guard: $1 per run, $3 in all, counted after every call, total on disk → one tiny key check ($0.000004) → code committed and tagged `haiku-frozen-4b` → both systems on dev, then once each on the same 20 test questions, with no changes in between → every answer scored complete on all five systems read blind by two fresh agents → [final-report.md](final-report.md) and [models.md](models.md) → README and project goal updated.

**Key numbers:**

| Measure | Dev: v2 | Dev: agent | Dev: one-shot Haiku | Dev: agent Haiku | Test: v2 | Test: agent | Test: one-shot Haiku | Test: agent Haiku |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Complete, read by hand | 9 of 26 | 12 of 26 | 15 of 26 | 17 of 26 | 5 of 16 | 4 of 16 | 10 of 16 | 10 of 16 |
| Of those, with a claim their sources don't support | 6 | 7 | 5 | 3 | 5 | 2 | 2 | 3 |
| Correct refusals | 4 of 6 | 5 of 6 | 5 of 6 | 5 of 6 | 1 of 4 | 3 of 4 | 4 of 4 | 4 of 4 |
| Wrong refusals | 0 | 1 | 3 | 0 | 1 | 2 | 1 | 0 |
| Median time | 63 s | 141 s | 12 s | 20 s | 49 s | 118 s | 10 s | 21 s |
| Cost of the run | - | - | $0.08 | $0.13 | - | - | $0.04 | $0.09 |

**Findings**
- **The first change to show up in complete answers on test.** Haiku doubles them: 5 to 10 on the one-shot, 4 to 10 on the agent, in the same direction on dev. Question by question, 24 are complete only on Haiku and 2 only on the local model, across both sets. The Writer really was the weak step.
- **The comparison I cared about most.** Complete answers with a claim their sources don't support, both sets together: one-shot 11 of 14 local, 7 of 25 Haiku; agent 9 of 16 local, 6 of 27 Haiku. Answers are about the same length, so it isn't because Haiku says less. Most of Haiku's are labels and scopes, but `single-06` reverses a rule.
- **With Haiku the agent earns less.** 10 against 10 on test and 17 against 15 on dev, at about twice the time and cost. It buys a little more reach and no wrong refusals where one-shot Haiku has 4.
- **Haiku doesn't tell υπερεργασία from υπερωρία.** On `reference-01` both Haiku systems give the 25% for υπερεργασία as the answer on υπερωρίες, and neither names Ν. 435/1976. The local systems do the same, and the chunks pointing to that law never reach any Writer.
- **It costs almost nothing here.** $0.35 in all against a $3 limit. The guard never had to stop anything. Most of Haiku's output is thinking, billed as output: about 2,300 tokens a call in the first trial, more than estimated.
- **Correction:** the blind read moves dev again. Both readers fail `single-23` on the three local systems, and pass the baseline's `sector-03` and v2's `single-27`, which I had failed. The agent goes from 13 to 12. Phase 3C's 15 against 12 is now 12 against 9. Every test verdict from Phase 4A stood.

**Decisions:** local by default, cloud optional, and the README says clearly that with Haiku the question and the law chunks leave my machine. Same prompts, the model's defaults, nothing tuned, so runs aren't exactly repeatable. Where both readers agree their verdict stands, even over the earlier one; where they differ, a ruling that says so. `labour_rag.ask` and `labour_rag.agent` stay local: only measuring runs use Haiku.

**Lessons**
- Move the part that's actually failing. Search work took three phases and didn't change complete answers on test. Changing the Writer did, in about a day, for $0.35.
- Check who is marking the work. The blind readers are Claude, and so is Haiku. Hidden labels don't hide a writing style, so this result needs a human reader before I fully trust it.
- A small, cheap trial before freezing code catches what estimates miss. One question each showed the thinking cost before any full run.
- A larger fresh test set is now the most useful next step: only large gaps mean much on 16 questions.

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
