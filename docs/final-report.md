# Final report: one-shot against the agent

Phase 4A. Three systems, the same questions, the same local Writer. `scripts/final_report.py` writes this file from the stored runs, so don't edit it by hand.

**In short.** On the dev questions, which I used while building the agent, it is ahead: 13 of 26 answers complete, against 9 for one-shot v2 and 6 for the Phase 2 baseline. On the test questions, which no system was tuned on, that lead is gone: 4 of 16, against 5 and 5. That is a gap of one answer, so the test doesn't show that the agent is worse. It shows that the lead on dev can't be taken at face value. The agent does refuse better on both sets (3 of 4 on test, against 1 and 2), and it takes about 2.4 times as long as one-shot v2. On v2 and the agent, most failures are the Writer's.

## The three systems

| System | How it answers | Search |
|---|---|---|
| Phase 2 baseline | Searches once and answers | bge-m3, semantic and keyword search mixed by equal-weight RRF, at most 2 chunks per act, the old repeat filter |
| One-shot v2 | Searches once and answers | qwen3-embedding:4b, semantic only, at most 2 chunks per act, repeats judged by numbers with a unit |
| Agent | Search, Judge, up to 3 rounds, Writer, citation check | The same search as v2 with at most 4 chunks per act, frozen at the tag `agent-frozen-3c1` |

All three use the same Writer: `ministral-3:8b`, with the same prompt and settings. So the differences come from what reaches the Writer, not from the Writer.

## The numbers

Dev has 32 questions: 26 can be answered and 6 must be refused, and 27 have a known right chunk. Test has 20: 16 and 4, and 17 with a known right chunk.

| Measure | Dev: baseline | Dev: v2 | Dev: agent | Test: baseline | Test: v2 | Test: agent |
|---|---:|---:|---:|---:|---:|---:|
| **Complete answers, read by hand** | **6 of 26** | **9 of 26** | **13 of 26** | **5 of 16** | **5 of 16** | **4 of 16** |
| Complete answers, by the matcher alone | 9 of 26 | 12 of 26 | 16 of 26 | 7 of 16 | 6 of 16 | 5 of 16 |
| Key facts found | 51% | 68% | 78% | 60% | 69% | 66% |
| Correct refusals | 4 of 6 | 4 of 6 | 5 of 6 | 2 of 4 | 1 of 4 | 3 of 4 |
| Wrong refusals | 2 of 26 | 0 of 26 | 1 of 26 | 2 of 16 | 1 of 16 | 2 of 16 |
| Right chunk reached the Writer | 13 of 27 | 22 of 27 | 24 of 27 | 12 of 17 | 15 of 17 | 14 of 17 |
| Time per question (median) | 36 s | 63 s | 141 s | 54 s | 49 s | 118 s |
| Failures: search | 13 | 4 | 2 | 5 | 1 | 0 |
| Failures: Judge | - | - | 1 | - | - | 3 |
| Failures: Writer | 9 | 15 | 11 | 8 | 13 | 10 |
| Failures: all | 22 | 19 | 14 | 13 | 14 | 13 |

- **Complete answers, read by hand.** The matcher looks for every key fact, but it can't read meaning. So I read every answer it scored complete, and took away those that state a key fact wrong or leave one out, short answer included. I didn't read the other test answers, so the matcher's misses stay as failures on all three systems.
- **Right chunk reached the Writer.** The chunk that holds the answer was among those the Writer received.
- **Time** is the median for one question, from one run on one laptop. The baseline's runs are from the day before, and Phase 2 already noted that their times are weak.
- **Failures** add up to the questions minus complete answers and correct refusals. *Search:* the right chunk never reached the Writer (one-shots) or the Judge (agent). *Judge:* it held back the right chunk, or let through a question that should have been refused. *Writer:* it had the right chunk and still fell short. One-shots have no Judge, so answering a question that should have been refused counts as the Writer's.

## What it shows

- **The lead on dev didn't carry over.** Complete answers go 6, 9, 13 on dev, and 5, 5, 4 on test. Key facts go 51%, 68%, 78% on dev, and 60%, 69%, 66% on test. Dev isn't a fair place for the agent: I built its rules while reading those answers, and tuned the matcher on them. Test is the fairer number, but a small one (see the next section).
- **Refusing is where the agent leads on both sets.** 5 of 6 on dev against 4 and 4, and 3 of 4 on test against 2 and 1. It refuses wrongly about as often as the others, 2 of 16 on test against 2 and 1. Those two, `single-25` and `vocab-04`, were the Judge's, with the right chunk in places 1 and 2 of the search.
- **Better search alone doesn't give better answers.** On test, the right chunk reaches the Writer for 15 of 17 on v2, against 12 on the baseline, and key facts rise from 60% to 69%. Complete answers stay at 5.
- **The Writer is now the weak step.** On test it causes 13 of v2's 14 failures and 10 of the agent's 13, and search causes 1 and 0. Three of v2's 13 are questions it should have refused, with no Judge to catch them, so on the questions that can be answered both have 10. Some of those may be the matcher's misses, because test answers scored incomplete weren't read. `single-06`, `single-22` and `single-31` are complete on both one-shots and not on the agent, whose Writer had the right chunk for all three. I haven't read those three answers, as the rule for the test split says.
- **The agent costs time.** The median is 118 s against 49 s on test, and 141 s against 63 s on dev. The Judge takes 79% of the agent's time on test.
- **Complete doesn't mean right in every sentence.** Of the 14 test answers that pass the hand read, 12 say something else their source doesn't support ([listed below](#other-mistakes-in-the-test-answers-that-pass)). They don't count under the rule, but anyone relying on these answers should check the source. The agent has such mistakes in 2 of its 4 answers, the one-shots in all 10. Both readers noted the same ones. I didn't plan to measure that, and the count is small, so it's a lead and not a result.

## How little this can show

**20 questions is few.** 16 can be answered, so one answer is about 6 points. 4 must be refused, so one refusal is 25 points. No two systems differ by more than 1 complete answer on test.

Taking the same questions one by one, and leaving out those where both are complete or neither is:

| Compared | Set | Complete only on the first | Complete only on the second | Chance of a split this uneven if they were equally good |
|---|---|---|---|---:|
| agent against v2 | dev | 6 | 2 | 0.29 |
| agent against baseline | dev | 8 | 1 | 0.04 |
| v2 against baseline | dev | 5 | 2 | 0.45 |
| agent against v2 | test | 2 | 3 | 1.00 |
| agent against baseline | test | 2 | 3 | 1.00 |
| v2 against baseline | test | 1 | 1 | 1.00 |

Only the agent against the baseline on dev stands out, and that is the set the agent was built on.

- **Test looks easier than dev.** The same baseline has 23% of answers complete on dev and 31% on test, and the right chunk reaches its Writer for 48% and 71%. Compare systems within a set, not across sets.
- **One run each.** A fixed seed makes a run repeatable, not typical. In Phase 3C.1, two small fixes changed 6 of 32 answers.
- **Two readers, no lawyer.** I (Claude) read the test answers blind: labels hidden, the answers to each question shuffled, verdicts saved before I opened the key. A fresh Claude agent then read the same 18 the same way, without my verdicts. We agreed on 17. On the baseline's `single-08` I had passed it and the second reader failed it, and its reasoning holds, so it fails here. That change came after the labels were open. Both readers are the same model, and the style of an answer can still give a system away, so this is not a fully independent check. The dev read had one reader and wasn't blind, so it may be a little generous too.
- **The order depends on close calls.** With the baseline's `single-08` still complete, test would read 6, 5 and 4. Both `single-22` answers and the baseline's `single-31` stay complete under the rule, each with a wrong statement right next to the key facts. If those failed, it would read 3, 4 and 4. So the order of the three on test means little.
- **I wrote the test set.** The owner reviewed 20 of its 52 items. Its expected answers follow our 1852-1999 data, not today's law.
- **Hand reading only takes away.** Answers scored incomplete weren't read on test. If the matcher missed a right answer, that answer stays a failure.
- **This test is now used.** I have read its complete answers. A later system can still make its own one run on it, but no change may come from what those answers say, and a clean second test needs new questions.

## Failures by step

Test answers are listed by id only. Those scored incomplete weren't read.

| System | Set | Search | Judge | Writer |
|---|---|---|---|---|
| baseline | dev | 13: `lookup-01`, `reference-02`, `sector-05`, `single-09`, `single-10`, `single-14`, `single-17`, `single-21`, `single-29`, `vocab-01`, `vocab-02`, `vocab-03`, `vocab-06` | - | 9: `lookup-03`, `reference-01`, `refuse-06`, `sector-01`, `sector-02`, `sector-03`, `single-02`, `single-18`, `single-32` |
| v2 | dev | 4: `lookup-01`, `sector-05`, `single-09`, `vocab-01` | - | 15: `lookup-03`, `reference-01`, `reference-02`, `refuse-06`, `sector-01`, `sector-03`, `single-10`, `single-11`, `single-14`, `single-17`, `single-18`, `single-27`, `vocab-02`, `vocab-03`, `vocab-06` |
| agent | dev | 2: `lookup-01`, `vocab-01` | 1: `reference-01` | 11: `reference-02`, `sector-01`, `sector-02`, `sector-03`, `single-01`, `single-09`, `single-10`, `single-14`, `vocab-02`, `vocab-03`, `vocab-06` |
| baseline | test | 5: `lookup-02`, `sector-04`, `single-03`, `single-25`, `vocab-04` | - | 8: `reference-03`, `refuse-05`, `sector-06`, `single-04`, `single-05`, `single-08`, `single-12`, `single-19` |
| v2 | test | 1: `lookup-04` | - | 13: `reference-03`, `refuse-02`, `refuse-05`, `sector-04`, `sector-06`, `single-03`, `single-04`, `single-05`, `single-08`, `single-12`, `single-19`, `single-25`, `vocab-04` |
| agent | test | 0 | 3: `reference-03`, `single-25`, `vocab-04` | 10: `sector-04`, `sector-06`, `single-03`, `single-04`, `single-05`, `single-06`, `single-08`, `single-19`, `single-22`, `single-31` |

## Answers scored complete that fail when read

| System | Set | Question | Why it fails |
|---|---|---|---|
| baseline | dev | `sector-02` | Its short answer allows overtime «πέραν των 120 ωρών ετησίως». The limit is at most 120 hours a year. |
| baseline | dev | `sector-03` | It limits the rates to bakeries making over 3,000 okades of bread. The chunk says «παντός είδους αρτοποιεία». |
| baseline | dev | `lookup-03` | It says the law makes 1 May a holiday. The law says it can be made one by a minister's decision, each year. |
| v2 | dev | `single-17` | Its short answer turns the exception around: dismissal depends on how long a health stoppage lasts. The key fact is a serious reason, given in writing. |
| v2 | dev | `single-27` | It puts the Dormition on 21 August. |
| v2 | dev | `lookup-01` | "Subject to article 3" isn't there: the matcher took a list number "3." for it. The right chunk wasn't among its 8, so this counts as a search failure. |
| agent | dev | `single-10` | It starts the six months from the payment. The chunk says «αφ' ης κατέστη απαιτητή». |
| agent | dev | `sector-01` | It says 5 days for six years of service. The chunk says 30. |
| agent | dev | `sector-02` | It says «δεν απαιτεί προηγούμενη άδεια». The chunk says «μόνον κατόπιν αδείας». |
| baseline | test | `single-08` | The key fact names four years of service. The answer never says that, and says the law protects those with «περισσότερους από τέσσερις μήνες». I passed this at first: the second reader failed it, and that reading is right. |
| baseline | test | `single-12` | It says the 24 hours end at 24:00 «της επόμενης ημέρας». The chunk has them start at 00:01 and end at 24:00 the same day. |
| v2 | test | `single-25` | Its short answer opens with «Δεν χρειάζεται αποζημίωση» for a week away, unless the stoppage is over four days. A week is over four days, so the rule gives this person the opposite, and the explanation hedges instead of saying yes. |
| agent | test | `single-08` | It never says the illness must be proved. Its short answer skips those words with "…", and the matcher took «αποδεικνύει εγκατάλειψη», about something else, for that fact. |

## Other mistakes in the test answers that pass

These are outside the key facts, so they don't count against an answer. The agent's `lookup-02` and `vocab-05` had nothing to note.

| System | Question | What else is wrong |
|---|---|---|
| baseline | `lookup-04` | It ties the duty to safety and health and to directive 93/104. The chunk's last words are the heading of the next article. |
| baseline | `single-06` | The quote is invented: «πέντε έτη» isn't in the law, which says «τετραετή». The citation check catches this one. |
| baseline | `single-22` | **Close call.** The key facts are right, but it says a safety technician isn't obligatory for 20 to 49 people. Paragraph 2 of the same chunk says the employer must use one. It also turns a qualification rule for shipyards into a duty. |
| baseline | `single-31` | It says the law doesn't state whether the extra leave is on top of normal leave. Its own quote says «επί πλέον της νόμιμης». |
| baseline | `vocab-05` | It names the wrong law: Π.Δ. 119/1973, about bus staff, citing a chunk that doesn't hold the quote. The words are from Β.Δ. 748/1966 art. 14. |
| v2 | `lookup-02` | It adds that workers can withdraw a dismissal and go to court for it. The chunk doesn't say that. |
| v2 | `single-06` | One line says "more than four months" of service where the law says four years; the next line has it right. It says the whole law was replaced, and only article 1 was. |
| v2 | `single-22` | **Close call.** The key facts are right, but the short answer says "full-time employment". The chunk's minimum is 75 hours a year, as its own next line says. It also invents a rule about doctors by risk category. |
| v2 | `single-31` | It says normal leave doesn't grow with the years. Α.Ν. 539/1945 art. 2 says it does, up to a limit. |
| v2 | `vocab-05` | It adds a three-day suspension as a penalty, from a rule about bus staff. |
| agent | `lookup-04` | It says the duty is under the safety and health provisions. The chunk says under current legislation. The same heading trap as the baseline's. |
| agent | `single-12` | It adds that collective agreements may shorten the rest. The cited chunk doesn't say that. |

## How the runs were made

- **The guard.** `labour_rag/evaluate.py` now lets exactly two systems use the test split, once each, and only with their own settings: `oneshot-v2` and `agent`. The baseline keeps its Phase 2 run. Any other system or setting is refused.
- **The freeze.** `git diff agent-frozen-3c1 -- labour_rag prompts sql ':!labour_rag/evaluate.py'` printed nothing before the agent's run and after it. `evaluate` checks this itself, also when it continues an interrupted run, and refuses to start if anything changed.
- **The runs.** Both ran on 2026-11-05, detached from the session, one after the other, with no other model job. Each answered all 20 questions: v2 in about 17 minutes, the agent in about 52. An interrupted run would have continued where it stopped.
- **A correction.** Reading all three systems by one rule changed an earlier number. The Phase 3C report said 15 complete answers against 12 on dev. It's 13 against 9: my first read was too generous. [The agent report](agent-report.md) is corrected.

## What comes next

Phase 4B replaces the Judge and the Writer with Claude Haiku, with a budget guard in code. The numbers above are a reason to try it, because the Writer is the weak step. They also limit what it can prove: dev isn't a fair set, and 16 test questions can't show a gap of a few answers.
