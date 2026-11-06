# Lessons learned

What this project taught, technical and process. Each lesson has the numbers behind it. For what was decided because of them, see [Decisions](decisions.md). The numbers are in the [final report](final-report.md).

## Data is the ceiling

No model can answer from a law that isn't there. The dataset was built for topic classification, not to hold complete legal texts. Only 445 of its 1,284 labour documents are divided into articles, 468 are only a title, and 700 laws are mentioned without being in the data ([list](missing-laws.md)).

The overtime question shows it. The general rate is in Ν. 435/1976, which is only mentioned. The right answer is a refusal that says so. All five systems answer with a sector's rate instead, so all five fail `reference-01`.

**A test set written from the data can't see this.** Our expected answers follow the data, so a missing law shows up as "should refuse", and refusing it scores as a success. Scores here say how well the system uses what it has. They say nothing about how useful that is to someone with a question about their job today.

## Measure instead of following rules of thumb

Most of what seemed obvious at the start didn't hold on these questions:

| Rule of thumb | What happened here |
|---|---|
| Hybrid search beats semantic search | Semantic alone reached the right chunk for 22 of 27 dev questions, equal-weight RRF for 14. Two lines of arithmetic showed why: any chunk in both lists beats the first of either. |
| Rewrite the query before searching | 22 of 27 with or without it, for about 7 seconds per question. |
| A better embedding fixes search | Only after the fusion was fixed. Through the old fusion, qwen3 gained 1 question. Through the new one, 5. |
| More chunks per law, better answers | Limit 4 brought 3 more right chunks, and complete answers by the matcher fell from 9 to 7. |
| More rounds help | In Phase 3C, of 9 questions that searched again, 1 got better, 2 got worse and 6 didn't change. |
| Better search gives better answers | On test, the right chunk went from 12 to 15 of 17, and complete answers stayed at 5. |
| 2,560 dimensions can't use HNSW | They can, on `halfvec`. And at this size the index saves about 12 ms, so it was never the question. |
| The cloud is slower | Here a median question took 10 to 21 s on Haiku, and 49 to 118 s on one laptop. |

None of this is general. It's these questions, this model and this data. But checking took minutes or hours, and guessing would have cost whole phases.

## The bottleneck moves

Fix one step and the failures move to the next. Dev failures by step:

| | Search | Judge | Writer | All |
|---|---:|---:|---:|---:|
| Baseline | 13 | - | 9 | 22 |
| One-shot v2 (better search) | 4 | - | 15 | 19 |
| Agent (adds a Judge) | 2 | 1 | 12 | 15 |
| Agent Haiku (better model) | 1 | 1 | 8 | 10 |

**From search to Writer: that's measured.** The search work of Phases 3A and 3B moved failures to the Writer without changing complete answers on test. Then replacing the model took them from 5 to 10 of 16 on the one-shot, Writer only, and from 4 to 10 on the agent, Judge and Writer, in about a day, for $0.35.

**From Writer to data: that's a judgement, not a measurement.** The Writer is still the largest label: 8 of agent Haiku's 10 failures on dev, and all 6 on test. Some of those may be the matcher's misses, since test answers it scored incomplete weren't read. Two of the 10 on dev are plainly about data: `reference-01` (the law is missing) and `vocab-01` (only the title is there). The failure labels have no "data" category, and the test set can't see data gaps, as the first lesson says. The case for data as the next limit rests on the 700 missing laws and the 1999 cut-off, not on these labels.

Diagnostic question for any failure: was the answer in the chunks the model received? No is a search problem. Yes is a reading problem. It's worth asking before buying a better anything.

## The Judge's value shrinks with a strong Writer, but not everywhere

What the agent adds over the one-shot, on each model, both sets together:

| What it adds | On the local model | On Haiku | |
|---|---:|---:|---|
| Complete answers | 14 → 16 | 25 → 27 | The same gain |
| Complete answers with an unsupported claim | 79% → 56% | 28% → 22% | Shrinks |
| Correct refusals, of 10 | 5 → 8 | 9 → 9 | Goes away |
| Right chunk reached the Writer, of 44 | 37 → 38 | 37 → 41 | Grows |
| Wrong refusals, of 42 | 1 → 3 (worse) | 4 → 0 (better) | Reverses |

So what shrinks is the Judge's work as a filter: a strong Writer needs less protection from bad chunks and refuses well by itself. What's left is reach, and a guard against the Writer refusing because search fell short. Whether that's worth twice the time and cost depends on what a wrong refusal costs you.

`agent-mixed`, the same local Judge with a Haiku Writer, is the clearest test. The Judge made the same decisions on all 32 dev questions, so the same chunks reached both Writers, and complete answers went from 12 to 17. **Swapping both models showed that Haiku helps. Swapping only the Writer, on dev, showed that it brings the gain in complete answers.** The reverse swap wasn't run, and dev flatters the local Judge.

**Rules depend on the model that met them.** The stop rule was built for a Judge that keeps searching. On dev it fired 5 times on the local Judge and never on Haiku's.

## Small samples and moving verdicts

- **One answer is about 6 points on test.** Only 16 test questions can be answered, and one refusal is 25 points.
- **Only large gaps mean anything.** Of 12 question-by-question comparisons, one falls below 0.05 (0.03), and with 12 tries one like that could turn up by chance. What gives it weight is that all four Haiku-against-local comparisons point the same way: 24 questions complete only on Haiku, 2 only on the local model. They share questions and a Writer, so that isn't 26 separate results.
- **A lead on the questions you built with isn't evidence.** The local agent leads 12 to 9 on dev and trails 4 to 5 on test.
- **The same answers can get a different score.** One figure went from 15 against 12, to 13 against 9, to 12 against 9, with no new complete answer. Only the reading changed: first too generous, then by one rule for all systems, then blind.
- **The order can depend on close calls.** In Phase 4A one verdict either way gave 6, 5, 4 on test, and stricter readings of three others gave 3, 4, 4.
- **Size the test set before comparing systems.** It's the one thing here that's expensive to fix afterwards, because a read test set can't be read fresh.

## Claude reading Claude

This is the largest doubt in the project. Claude Code drafted the test set, and the owner reviewed 20 of its 52 items. Two fresh Claude agents read all 111 answers scored complete, with labels hidden and answers shuffled, and agreed on 109. Two of the five systems they compared run on a Claude model.

- **High agreement isn't proof,** because they're the same model. A later pair matched every earlier verdict on 41 answers, apart from one disagreement between them. That shows a model agreeing with itself, not independent readers.
- **Hidden labels don't hide a style.** A reader can tell two kinds of writing apart, and the local answers do read differently. Readers may favour Haiku's style, and nothing here can rule that out.
- **A ruling can't be fully blind either.** On `single-04` the readers differed. The one ruling on it could work out the answer was Haiku's, so it took the stricter side. If that answer passed, one-shot Haiku would have 11 of 16.
- **It still beat one reader.** A blind second reader found mistakes in the first reading, including answers wrongly failed and wrongly passed. It's cheap and worth doing, as long as nobody mistakes it for a person.

Only a human reader on a fresh test set can remove this doubt.

## The freeze discipline

Tags that mark what was measured, a check in code that refuses a run if anything that decides an answer changed, and one test run per system.

**What it gave:** every test number since Phase 4A names exact code. After the first results it was tempting to adjust things, and the check made that a visible act, not a quiet one.

**What it cost:** a mistake found after a test run can only be reported. The `--haiku` flag had to be confined to `main()`, and the freeze check made exact enough to prove that. Tracing needed a separate command, because the plain commands run only frozen code. All of that was cheaper than not knowing what a number means.

**It also forced better engineering.** Phase 5 had to wrap the model client and graph nodes from outside, and that left tracing in one file that the rest of the code doesn't know about.

## What tests missed and only the real thing showed

The tests passed through each of these:

- **Phoenix refused every trace.** It asks for a login inside a container, so every span got a 401. The tests use a list in memory where the viewer would be. A warning in a real run showed it.
- **A name clash hid the attribute that explains searching again.** `labour.round` next to `labour.round.judge_said`: Phoenix nests dotted names, so filters on the second found nothing. Only the real viewer showed it. There's a test for it now, and that test could only be written after seeing it.
- **Phoenix crashed on start,** because its non-root user couldn't write to a new volume.
- **The first Phoenix screenshot looked fine, and it wasn't the trace at all.** Look at the picture.
- **The Mac went to sleep during a call.** One Judge span took 1,974 s where the same question takes about 30 s, with the usual tokens. Tests don't sleep.
- **An empty key came out as "Connection error. Is Ollama running?"** That's true of nothing. A guard should fail for the right reason, so check what a failure really says.
- **A false claim about a missing law.** The Judge named the decree it was reading, and the code said its text wasn't in the data. A trial run caught it, and it's the worst mistake this system can make.

Tests are good at logic with known answers. They only see what you already thought of. After changing anything that talks to something else, use the real something else.

## Read the answers

- **A score can hide a wrong answer.** `sector-01` counted as complete while telling a worker with six years "5 days" where the rule says 30.
- **"Citation check passed" doesn't mean correct.** On the Phase 2 baseline, by the matcher, 4 of the 11 passing answers had every key fact, against 5 of the 15 failing ones. It proves words exist, not that the reasoning follows.
- **A complete answer can still say things its sources don't.** 17 of the 34 test answers that pass a hand read do, and on `single-06` one-shot Haiku reverses a rule outside the key facts.

## Write it down, then check it

- **Plain words find mistakes.** A line-by-line check of [How a question is answered](how-a-question-is-answered.md) against the code found 3 false statements, and a fresh read found 13 more mistakes. They all sounded right.
- **Hand-written numbers drift, and generated ones don't.** The final check for this page reran the report scripts, and their numbers held. The numbers that had gone stale were typed by hand: a package count, a timing, test counts, one question count. Where a report's script stops if a claim stops holding, nobody has to remember.
- **Read a tool's settings before trusting it with your data, even a local one.** Phoenix reports its usage unless told not to, and the Anthropic SDK could send a trace id in a header. All of that is off now.
- **Long runs need `caffeinate`,** and a run started from a session can die with it. Save each result as it finishes, so stopping costs nothing.
