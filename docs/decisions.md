# Decisions

Every architecture decision in one place, each with why it was made, the evidence and what else was considered.

- **Numbers** come from the linked reports, unless a line says it was checked on 2026-11-06 for this page.
- **"Not measured"** means no run compared the options, so the choice rests on reasoning alone.
- **Dev** is the 32 questions used while building. **Test** is the 20 kept aside: 16 can be answered and 4 must be refused. One test answer is about 6 points, so small gaps mean little.
- **Complete** means every key fact is there and none is wrong, as read by two blind readers. Both are Claude models, which is the biggest doubt about these numbers: see [Lessons](lessons-learned.md#claude-reading-claude).

**Data and storage:** [Postgres in Docker](#local-postgres-in-docker) · [Chunks](#chunks-per-article-with-a-contextual-header) · [qwen3](#qwen3-over-bge-m3) · [HNSW](#an-hnsw-index-on-both-embedding-tables) · [Scope](#laws-after-1999-are-out-of-scope)

**Search:** [Semantic first](#semantic-first-instead-of-rrf) · [Repeats and limits](#a-repeat-filter-and-a-limit-per-act) · [Enhancer](#the-enhancer-only-as-a-second-try)

**The agent:** [LangGraph](#langgraph-for-the-loop) · [Judge and rounds](#a-judge-at-most-3-rounds-and-a-stop-rule) · [Refusals](#refusals-written-by-code) · [Citations](#citations-checked-in-code) · [No checkpointer](#no-checkpointer)

**Models:** [Local model](#one-small-local-model-for-every-local-role) · [Haiku optional](#haiku-optional-local-by-default) · [Haiku for demos](#haiku-as-judge-for-demos) · [Budget guard](#a-budget-guard-in-code)

**Measuring:** [Test split and reading](#one-test-run-per-system-read-by-hand) · [Freeze](#freeze-tags-and-a-freeze-check)

**Observability:** [Own spans](#own-spans-sent-to-jaeger-and-phoenix) · [The traced wrapper](#tracing-through-a-wrapper-with-the-plain-commands-untraced)

---

## Local Postgres in Docker

- **Decision:** Postgres 17 with pgvector 0.8.6, in Docker, on `127.0.0.1:5433`. One database holds the text, the vectors and the keyword index.
- **Why:** one compose file rebuilds it anywhere, and semantic and keyword search share one table and one query language. Port 5433 leaves the Postgres.app on 5432 alone.
- **Evidence:** labour law is small: 5,740 chunks and 111.9 MB with bge-m3 ([search report](search-report.md#database-size)), and 185 MB with both embeddings (checked on 2026-11-06). The database part of a search takes milliseconds.
- **Alternatives:** Postgres.app, already on the machine, whose port is taken. Supabase's free plan: labour law fits in its 500 MB and the full dataset, an estimated 3.2 GB in the database, doesn't. It only matters for hosting ([data exploration](data-exploration.md#size-estimate-for-the-database-decision)). A dedicated vector database wasn't considered, because nothing here needs one.

## Chunks per article, with a contextual header

- **Decision:** cut at article markers, then numbered paragraphs, then size. Short documents stay whole. Pieces under 20 words join the one before, and pieces over 500 words become windows sharing about 50 words. Each chunk gets a header for embedding and keyword search: citation, article and title of the act.
- **Why:** the article is the unit people cite. The text alone often doesn't say which law it belongs to, so every chunk has to carry that address.
- **Evidence:** 5,740 chunks, median 81 words. The 445 documents cut by article give 4,338 of the chunks, 140 by paragraph give 678, 13 by size give 38, and 686 stay whole. 1,222 headings moved to the article they belong to ([chunking report](chunking-report.md#at-a-glance)). **Not measured:** no run compared with and without the header, or other sizes. A known fault: article 2 of Ν. 1837/1989 sits inside a chunk labelled "Άρθρο 18", and `lookup-01` fails on every system but agent Haiku.
- **Alternatives:** cutting long articles at 300 or 800 words, estimated in Phase 0 at 5,906 and 5,082 chunks and never run. Plain fixed-size windows and chunking by meaning weren't considered, because the law already has a structure.

## qwen3 over bge-m3

- **Decision:** `qwen3-embedding:4b` is the default, in its own table. `bge-m3` stays selectable. This was the project owner's decision after Phase 3A.
- **Why:** the right chunk reaches the Writer more often.
- **Evidence:** with semantic search, 22 against 17 of 27 dev questions at limit 2, and 23 against 19 at limit 4. It gains 6 questions and loses 1, a split chance alone would give about 12% of the time, so this is suggestive only. The cost: about 2.5 hours to embed against 5 minutes, and about 0.12 s per search against 0.03 s ([retrieval report](retrieval-report.md#does-qwen3-beat-bge-m3)).
- **Alternatives:** staying on bge-m3, measured. qwen3 without its query instruction reaches 21 and 23, so the result doesn't depend on it. Other embedding models weren't tried.

## An HNSW index on both embedding tables

- **Decision:** both tables have an HNSW index with cosine distance. qwen3's column is `halfvec(2560)`, and `bge-m3`'s is `vector(1024)`. Semantic search switches sequential scans off around its query and uses `hnsw.ef_search = 100`.
- **Why:** 2,560 dimensions don't rule HNSW out, but they do rule out the plain `vector` type. Trying it in the running database: `vector(2560)` fails with "column cannot have more than 2000 dimensions for hnsw index", `halfvec(2560)` builds, and `halfvec(4001)` fails at the limit of 4,000. The seqscan switch is there because the vectors are stored out of line, and the planner doesn't count that cost ([search report](search-report.md#search-speed)).
- **Evidence:** checked on 2026-11-06. The indexes `chunk_embeddings_qwen3_4b_hnsw` and `chunks_embedding_hnsw` exist, 45 MB each, and the query plans use them. Against an exact scan on the 32 dev questions:

  | | With HNSW | Exact scan | Same top 8 | Same top 30 | Top 50 in common |
  |---|---:|---:|---:|---:|---:|
  | qwen3 | 7.8 ms | 20.3 ms | 31 of 32 | 28 of 32 | 99.2% |
  | bge-m3 | 2.9 ms | 10.0 ms | 29 of 32 | 25 of 32 | 98.6% |

- **At this size the index isn't needed for speed.** It saves about 12 ms, next to about 0.1 s for embedding the question and seconds to minutes for the answer, and it's approximate, so it can change a result. It stays because every measured run used it: the qwen3 index has been built since Phase 2. Removing it would change what those numbers describe.
- **Alternatives:** an exact scan, measured above: simpler, exact and fast enough, and the better default for a new project of this size. Plain `vector(2560)` can't be indexed. Cutting the vectors to 2,000 numbers wasn't tried.

## Laws after 1999 are out of scope

- **Decision:** the corpus is volume 41 of the dataset: 1,284 documents dated 1852 to 1999. Expected answers follow this data, not today's law. Every answer ends with a note saying so.
- **Why:** that's where the dataset stops. Mixing periods without labelling them would give confident wrong answers about current rights.
- **Evidence:** 700 laws are mentioned and not in our data, 274 of them in other volumes of the dataset, and 468 documents are only a title ([missing laws](missing-laws.md)). Questions about later laws are refused correctly by agent Haiku on 5 of 6 dev and 4 of 4 test must-refuse questions, which also include other topics ([final report](final-report.md#the-numbers)).
- **Alternatives:** adding Π.Δ. 80/2022 now, deferred to Phase 6, labelled by period ([backlog](backlog.md)). All 47 volumes: an estimated 3.2 GB in the database, and outside the question this project asks.

## Semantic first, instead of RRF

- **Decision:** the first search is semantic only. In the agent, keyword search takes up to 2 places after the first 6 when a law is named, and later rounds search by keyword for laws the Judge names. `--fusion rrf` on `ask` and `evaluate` brings back the old way.
- **Why:** with the constant 60 and 50 chunks per list, a chunk in both lists scores at least 2/110 = 0.0182, and the first chunk of one list scores 1/61 = 0.0164. Any chunk in both lists, even 50th in each, beat the top result of either list.
- **Evidence:** the right chunk reaches the Writer for 17 against 13 of 27 on bge-m3, and 22 against 14 on qwen3, at limit 2. MRR on qwen3 goes from 0.38 to 0.61 ([retrieval report](retrieval-report.md#the-table)). Chosen on the same 27 questions it's measured on.
- **Alternatives:** five were measured. At limit 2, on bge-m3 and on qwen3: equal-weight RRF (13 and 14), RRF with semantic counted double (15 and 19), semantic only (17 and 22), keyword only if a law is named (17 and 22), and 6 semantic places then 2 keyword (17 and 22). A rule fixed in advance chose the simplest within one question. That doesn't show keyword search is useless: on bge-m3 `sector-02` is 2nd there and 20th in semantic search, though on qwen3 it's 1st in semantic. And dev has only 2 questions with a right chunk that name a law, so this barely tests it.

## A repeat filter and a limit per act

- **Decision:** from the top 30, take 8 chunks, skipping repeats and chunks over the limit per act. A repeat shares 50% of its words with a kept chunk and states the same numbers with a unit (`16 εβδομάδες`, `10%`). Among repeats, the newest act takes the older one's place. The limit is 2 on the one-shot and 4 on the agent, because the Judge filters.
- **Why:** ILO clauses and decisions re-issued every year crowd the results. But chunks with different numbers state different rules, and the first filter hid a 16-week rule behind a 15-week one.
- **Evidence:** numbers with a unit removes 45 repeats and lets 8 near-identical pairs through in 5 questions. The right chunk stays at 22 of 27 on qwen3, and rises from 17 to 18 on bge-m3 ([enhancer report](enhancer-report.md#the-repeat-filter)). In Phase 2, limit 4 brought 3 more right chunks to the one-shot, and complete answers by the matcher fell from 9 to 7 ([eval report](eval-report.md#experiments-a-and-b-the-limit-per-document)).
- **Alternatives:** the literal "every digit" rule, measured: it removes 6 repeats and hands over 28 near-identical pairs in 9 questions, for the same right chunks. The old filter, which ignored numbers: of its 26 pairs, 14 differed in a number with a unit. **Not measured:** the agent at limit 2, so its gain can't be fully separated from limit 4 ([agent report](agent-report.md#the-result-of-phase-3c)).

## The Enhancer only as a second try

- **Decision:** the local model rewrites the question into searches in the words of the law only when a second search is needed. It makes one call, in round 2, and round 3 reuses the phrasings. The one-shot doesn't use it.
- **Why:** as a first step it costs seconds and adds nothing. It does search differently, so it has a use when the plain question has failed.
- **Evidence:** 22 of 27 with or without it, the very same questions, and 21 on its phrasings alone. It takes a median of 7.2 s per question. It never writes "εργοτάξια", the word `vocab-01` needs, and its katharevousa is often not real Greek ([enhancer report](enhancer-report.md#the-result)).
- **Alternatives:** running it first on every question, measured. Its phrasings together with the question, measured. A stronger model for it wasn't tried: it stays local on every system.

## LangGraph for the loop

- **Decision:** the agent is a LangGraph graph with five steps: search, judge, search again, write and refuse. LangSmith tracing is switched off before LangGraph is imported.
- **Why:** learning it was one of the project's goals, and the graph makes the routing easy to read and test.
- **Evidence:** the routing has its own tests with stand-ins for the database and models. The cost: 38 of the 53 pinned packages are LangGraph and what it brings. **Not measured** against anything.
- **Alternatives:** a plain Python loop would do for a graph this size. It wasn't built.

## A Judge, at most 3 rounds, and a stop rule

- **Decision:** a Judge gives each chunk a verdict, then answers, searches again or refuses. The Writer sees only approved chunks and the person's own question. There are at most 3 rounds, and the last round's schema can't say `search_again`. If the Judge asks to search again but an approved chunk is relevant and applies, the code writes instead.
- **Why:** Phases 1C and 2 showed answers built on rules for other groups, and too few refusals: none in 1C, and 6 of the 10 due on the Phase 2 baseline. Phase 3C showed searching on after the answer was in hand, and the Judge undoing its own right decision.
- **Evidence, for the Judge:** on the local model, 12 against 9 complete on dev, but 4 against 5 on test, so the dev lead doesn't carry over. Correct refusals 8 against 5 of 10, wrong refusals 3 against 1, both sets together. The Writer reads 3.4 chunks against 7.9. A median question takes 141 s against 63 s ([final report](final-report.md#the-numbers), [agent report](agent-report.md#the-result-of-phase-3c)).
- **Evidence, for rounds and the stop rule:** in 3C, 9 questions searched again: 1 better, 2 worse, 6 the same. In 3C.1 the first real rescue arrived (`single-09`), and wrong refusals fell from 2 to 1. On dev, the stop rule fired 5 times, on a chunk that really answers only twice, and never on Haiku's Judge. Rounds used on dev: 26, 4 and 2 questions took 1, 2 and 3 ([agent report](agent-report.md#phase-3c1-the-two-fixes)).
- **Alternatives:** no Judge, measured as the one-shot. No stop rule, measured as 3C. More than 3 rounds: **not measured**. The limit was set at the start, and most questions don't reach it.

## Refusals written by code

- **Decision:** when the Judge refuses, or the last round has no approved chunk, the code writes the refusal, with no Writer call. It names a law as missing only after looking it up in the database, and a law the Judge names must be cited in the chunks. The Writer can still refuse by itself, as its prompt asks.
- **Why:** telling someone a law is missing when it isn't is the worst mistake here. A lookup can't invent that, and a model can.
- **Evidence:** all 11 such claims in the 3C run are true. A trial first caught a false one: the Judge named the decree it was reading, and the code called it missing. That's why a named law must be cited in the chunks ([agent report](agent-report.md#how-the-agent-works)). Correct refusals: 5 of 6 and 3 of 4 on the local agent, 5 of 6 and 4 of 4 on agent Haiku ([final report](final-report.md#the-numbers)).
- **Alternatives:** a model writing the refusal after the Judge refuses: **not measured**. It would add a call, and a chance to invent a law's absence. On the one-shots the model does write every refusal, with 5 of 10 correct locally and 9 of 10 on Haiku, but no report counts how often one misnames a law.

## Citations checked in code

- **Decision:** every `[n]` must exist. Every «quote» of three words or more needs a citation in its sentence and must appear in that chunk, ignoring accents and case. A failure shows the closest passage.
- **Why:** altered or invented quotes are easy to catch without a model, and they're common: in Phase 1C only 40% of quotes were in their chunk ([answer report](answer-report.md#at-a-glance)).
- **Evidence:** it catches what it's built for and proves little else. On the Phase 2 baseline, by the matcher, 4 of the 11 passing answers had every key fact, against 5 of the 15 failing ones ([eval report](eval-report.md#at-a-glance)). It can't see a claim that isn't a quote.
- **Alternatives:** a model checking whether each claim follows from its chunk: **not built**. The unsupported claims in the final report come from the blind readers, not from this check.

## No checkpointer

- **Decision:** `graph.compile()` takes no checkpointer. State lives only for one `invoke`, and nothing is remembered between questions.
- **Why:** one question goes in and one answer comes out. There's no conversation to remember and nothing worth resuming inside a question. A long `evaluate` run resumes between questions, from the results it has already stored. **Multi-turn questions would be the trigger** to change this ([backlog](backlog.md)).
- **Evidence:** the code, in `build_graph` in [`labour_rag/agent.py`](../labour_rag/agent.py). `langgraph-checkpoint` is installed only because LangGraph brings it. There's no number here, because nothing was compared.
- **Alternatives:** LangGraph's in-memory or Postgres checkpointers. Not tried.

## One small local model for every local role

- **Decision:** `ministral-3:8b` through Ollama is the local Judge, Writer and Enhancer, at temperature 0.2 or 0 with a fixed seed.
- **Why:** it runs on one laptop, and fixed settings make its answers repeatable.
- **Evidence:** it turned out to be the weak step: swapping it for Haiku as Writer took complete answers on the same chunks from 12 to 17 of 26 on dev ([final report](final-report.md#does-the-judge-need-to-be-haiku)). It costs no money, and a median agent question takes 118 to 141 s.
- **Alternatives:** other local models **weren't compared**, which is a real gap. A larger local model might close some of the distance to Haiku.

## Haiku optional, local by default

- **Decision:** `claude-haiku-5-5` can be the Judge and the Writer, chosen per run with `--haiku` or `--system`. Search, embeddings and the Enhancer stay local. Same prompts, the model's defaults, no tuning. With Haiku, the question and the chunks leave the machine, and `--haiku` says so first. A measuring run with `--system` doesn't.
- **Why:** it should run with no account and send nothing anywhere unless asked. The chunks are public law texts, so sending them is a fair option to offer, but it has to be a choice.
- **Evidence:** on test, 10 and 10 complete against 5 and 4 of 16; on dev, 15 and 17 against 9 and 12 of 26. Complete answers with an unsupported claim, both sets: 7 of 25 against 11 of 14 on the one-shot, 6 of 27 against 9 of 16 on the agent. Test runs cost $0.04 and $0.09. Median 10 s and 21 s against 49 s and 118 s ([final report](final-report.md#the-numbers)). Runs aren't exactly repeatable, because the API takes no seed.
- **Alternatives:** Haiku as the default, rejected because it needs a key and sends data. Larger Claude models weren't tried: the question was whether a small cheap one changes anything.

## Haiku as Judge, for demos

- **Decision:** for a demo, use `agent --haiku`, with Haiku as both Judge and Writer.
- **Why:** it's much faster, and its decisions look slightly better. They don't look better for complete answers.
- **Evidence:** `agent-mixed`, a local Judge with a Haiku Writer, ran on dev only: 17 of 26 complete on both, 3 with an unsupported claim on both. Median 76 s against 20 s, whole run 58 minutes against 11, $0.05 against $0.13. "Slightly better decisions" rests on little: right chunk 25 against 24 of 27, and wrong refusals 0 against 2, of which only `lookup-01` is a real difference. On the stored test runs, the local Judge refused `single-25` and `vocab-04` with the right chunk in places 1 and 2, and Haiku's refused neither ([final report](final-report.md#does-the-judge-need-to-be-haiku)).
- **Alternatives:** `agent-mixed`: the same number of complete answers on dev, with 3 questions different each way, less than half the cost, and about 4 times slower. `ask --haiku`: faster, 15 of 26 on dev, and 4 wrong refusals across both sets where the agent has none.

## A budget guard in code

- **Decision:** $1 per run and $3 across Phase 4B, counted after every call, with the total on disk so a resumed run still counts. It stops cleanly before a call that could pass a limit. Manual `--haiku` runs have their own record and a $2 limit.
- **Why:** a loop that calls a paid API shouldn't depend on someone watching it. A limit in the Console is a second layer, not the first.
- **Evidence:** it never had to stop anything. All the measuring came to $0.41 of the $3 ([models](models.md)).
- **Alternatives:** the $10 monthly limit on the workspace alone, kept as well. It wouldn't stop a run, or say which one spent it.

## One test run per system, read by hand

- **Decision:** 52 questions with written key facts: 32 dev and 20 test. Each named system gets one test run, enforced in `evaluate`. Key facts are matched without a model. Every answer scored complete is then read by two blind readers, and where they differ it's a ruling that says so. An answer fails if it states a key fact wrong or leaves one out.
- **Why:** a score has to be cheap enough to run on every change, and a matcher can't read meaning: it passed an answer saying "5 days" where the rule says 30.
- **Evidence:** the matcher agrees with a hand check on 68 of 71 facts, on answers it was tuned on ([eval report](eval-report.md#how-it-is-measured)). The readers agreed on 109 of 111 answers ([final report](final-report.md#how-little-this-can-show)). Reading moved one figure from 15 against 12 to 13 against 9 to 12 against 9.
- **Alternatives:** the matcher alone, which overstates every system: 18 against 17 on agent Haiku's dev run, 16 against 12 on the local agent's. A model scoring everything wasn't tried. A human reader wasn't used, and that's the first item in the [backlog](backlog.md).

## Freeze tags and a freeze check

- **Decision:** the tags `agent-frozen-3c1` and `haiku-frozen-4b` mark what was measured. `evaluate` compares the code with them before any test run and any full Haiku run, and refuses if anything that decides an answer changed: `labour_rag/` except `evaluate.py`, `prompts/` and `sql/`. New files don't count. `ask.py` and `agent.py` are compared without their `main()`. A later change to the agent is a new named system with its own run.
- **Why:** a test number only means something if it describes the system it names, and the temptation to adjust after reading results is real.
- **Evidence:** the four test runs after the baseline passed it, and 0 frozen lines changed in Phase 5. `tests/test_evaluate.py` has a `FrozenCode` test class ([final report](final-report.md#how-the-runs-were-made)). The price is real too: the [wrapper](#tracing-through-a-wrapper-with-the-plain-commands-untraced) below exists because of it. It checks files, so the `CHAT_*` settings in `.env` stay a promise.
- **Alternatives:** discipline alone, which leaves nothing to show a reader. A copy of the code per system, which is heavier and drifts.

## Own spans, sent to Jaeger and Phoenix

- **Decision:** spans we write ourselves, in `labour_rag/tracing.py`, wrapping the model client and graph nodes from outside at run time. A private tracer provider. Two OTLP exporters in the SDK, with no collector. Standard `gen_ai.*` names where they exist, OpenInference names for Phoenix, `labour.*` for the rest. The viewers start only under a compose profile.
- **Why:** an auto-instrumentation library sees "a call to a model". It can't tell the Judge from the Writer, or see a verdict, and nothing instruments plain HTTP calls to Ollama. The private provider keeps the SDK and LangGraph from adding spans of their own.
- **Evidence:** the same span ids are in both viewers, so the vendor-neutral point holds. About 440 lines and 9 packages. Jaeger is 51 MB to download and about 40 MB of memory, Phoenix 323 MB and about 450 MB ([observability](observability.md)).
- **Alternatives:** auto-instrumentation, rejected for the reason above. A collector container, which adds a moving part for one local user. One viewer, which wouldn't show that OTLP is portable.

## Tracing through a wrapper, with the plain commands untraced

- **Decision:** `python -m labour_rag.traced {ask,agent,evaluate} …` runs the command as it is, with a trace if `TRACING` is on. The plain commands never trace, on purpose. This is the project owner's decision.
- **Why:** the plain commands run only frozen code, so a setting in `.env` can't reach them without changing their `main()`. Leaving them alone keeps the claim simple: the frozen code knows nothing about tracing.
- **Evidence:** with tracing off, real `traced ask` output matches plain `ask` apart from timings and one note on stderr. With it on and the viewers down, the question is still answered, with one warning ([observability](observability.md#how-its-built)).
- **Alternatives:** about two lines in each `main()`, plus `evaluate.py`. The freeze check would allow it for `ask` and `agent`. Declined: a separate command costs a few keystrokes, and it's obvious from the command line whether a trace is being recorded.
