# Final report: one-shot and agent, local and Haiku

Phases 4A and 4B. Five systems, the same questions, the same prompts. `scripts/final_report.py` writes this file from the stored runs and `eval/hand_read.json`, so don't edit it by hand.

**In short.** Replacing the local Judge and Writer with Claude Haiku is the first change in this project that shows up in complete answers on the test questions. Read by hand, complete answers on test go from 5 to 10 of 16 for the one-shot, and from 4 to 10 for the agent. On dev they go from 9 to 15 of 26, and from 12 to 17. Haiku's complete answers also say less that their sources don't support: on both sets together, 7 of 25 against 11 of 14 for the one-shot, and 6 of 27 against 9 of 16 for the agent. A full test run cost $0.04 and $0.09, and took less time than the local ones. With Haiku writing, the agent adds little to complete answers (10 against 10 on test, 17 against 15 on dev), but it makes no wrong refusals where one-shot Haiku makes 4. A dev-only diagnostic says the Judge needn't be Haiku for complete answers, but Haiku's Judge is about 4 times faster ([details](#does-the-judge-need-to-be-haiku)). These sets are still small, the test questions have been read before, and the readers are Claude models judging a Claude model: see [How little this can show](#how-little-this-can-show).

## The five systems

| System | How it answers | Search | Judge and Writer |
|---|---|---|---|
| Baseline | Searches once and answers | bge-m3, semantic and keyword search mixed by equal-weight RRF, at most 2 chunks per act, the old repeat filter | `ministral-3:8b`, local |
| One-shot v2 | Searches once and answers | qwen3-embedding:4b, semantic only, at most 2 chunks per act, repeats judged by numbers with a unit | `ministral-3:8b`, local |
| Agent | Search, Judge, up to 3 rounds, Writer, citation check | The same as v2 with at most 4 chunks per act, frozen at the tag `agent-frozen-3c1` | `ministral-3:8b`, local |
| One-shot Haiku | The same as one-shot v2 | The same as one-shot v2 | `claude-haiku-5-5`, cloud |
| Agent Haiku | The same as the agent | The same as the agent | `claude-haiku-5-5`, cloud |

All five use the same prompts. The local model runs at temperature 0.2 or 0 with a fixed seed. Haiku runs at its defaults: no temperature, no seed, thinking at its default effort. So it isn't only the model that changes, and Haiku's runs aren't exactly repeatable. **With Haiku, the question and the law chunks leave the machine.** The chunks are public law texts. Search, embeddings and the Query Enhancer stay local on every system.

## The numbers

Dev has 32 questions: 26 can be answered and 6 must be refused, and 27 have a known right chunk. Test has 20: 16 and 4, and 17 with a known right chunk.

| Dev | Baseline | One-shot v2 | Agent | One-shot Haiku | Agent Haiku |
|---|---:|---:|---:|---:|---:|
| **Complete answers, read by hand** | **6 of 26** | **9 of 26** | **12 of 26** | **15 of 26** | **17 of 26** |
| Of those, with a claim their sources don't support | 6 | 6 | 7 | 5 | 3 |
| Complete by the matcher alone | 9 of 26 | 12 of 26 | 16 of 26 | 16 of 26 | 18 of 26 |
| Key facts found | 51% | 68% | 78% | 78% | 85% |
| Correct refusals | 4 of 6 | 4 of 6 | 5 of 6 | 5 of 6 | 5 of 6 |
| Wrong refusals | 2 of 26 | 0 of 26 | 1 of 26 | 3 of 26 | 0 of 26 |
| Right chunk reached the Writer | 13 of 27 | 22 of 27 | 24 of 27 | 22 of 27 | 25 of 27 |
| Time per question (median) | 36 s | 63 s | 141 s | 12 s | 20 s |
| Time for the whole run | 20 min | 33 min | 94 min | 6 min | 11 min |
| Cost of the whole run | $0.00 | $0.00 | $0.00 | $0.08 | $0.13 |
| Failures: search | 13 | 4 | 2 | 4 | 1 |
| Failures: Judge | - | - | 1 | - | 1 |
| Failures: Writer | 9 | 15 | 12 | 8 | 8 |
| Failures: all | 22 | 19 | 15 | 12 | 10 |

| Test | Baseline | One-shot v2 | Agent | One-shot Haiku | Agent Haiku |
|---|---:|---:|---:|---:|---:|
| **Complete answers, read by hand** | **5 of 16** | **5 of 16** | **4 of 16** | **10 of 16** | **10 of 16** |
| Of those, with a claim their sources don't support | 5 | 5 | 2 | 2 | 3 |
| Complete by the matcher alone | 7 of 16 | 6 of 16 | 5 of 16 | 11 of 16 | 11 of 16 |
| Key facts found | 60% | 69% | 66% | 85% | 88% |
| Correct refusals | 2 of 4 | 1 of 4 | 3 of 4 | 4 of 4 | 4 of 4 |
| Wrong refusals | 2 of 16 | 1 of 16 | 2 of 16 | 1 of 16 | 0 of 16 |
| Right chunk reached the Writer | 12 of 17 | 15 of 17 | 14 of 17 | 15 of 17 | 16 of 17 |
| Time per question (median) | 54 s | 49 s | 118 s | 10 s | 21 s |
| Time for the whole run | 19 min | 17 min | 52 min | 3 min | 8 min |
| Cost of the whole run | $0.00 | $0.00 | $0.00 | $0.04 | $0.09 |
| Failures: search | 5 | 1 | 0 | 1 | 0 |
| Failures: Judge | - | - | 3 | - | 0 |
| Failures: Writer | 8 | 13 | 10 | 5 | 6 |
| Failures: all | 13 | 14 | 13 | 6 | 6 |

- **Complete answers, read by hand.** The matcher looks for every key fact, but it can't read meaning. So every answer it scored complete was read, and those that state a key fact wrong or leave one out were taken away, short answer included. Answers it scored incomplete weren't read on test, so its misses stay as failures on every system.
- **With a claim their sources don't support.** Among the complete answers: those with a side claim the chunks they cite don't support, as listed by both readers. One reader alone adds one more, on one-shot v2 on dev and on agent Haiku on test. [The next section](#unsupported-claims-local-against-haiku) has more.
- **Right chunk reached the Writer.** The chunk that holds the answer was among those the Writer received.
- **Time** is from one run on one laptop. Haiku's includes the network. The baseline's runs are from an earlier day, and Phase 2 already noted that their times are weak. **Cost** is real usage, counted after every call. Local models cost no money here.
- **Failures** add up to the questions minus complete answers and correct refusals. *Search:* the right chunk never reached the Writer (one-shots) or the Judge (agents). *Judge:* it held back the right chunk, or let through a question that should have been refused. *Writer:* it had the right chunk and still fell short. One-shots have no Judge, so answering a question that should have been refused counts as the Writer's.

## Unsupported claims: local against Haiku

| System | Dev: complete | With such a claim | Test: complete | With such a claim | Both: complete | With such a claim |
|---|---:|---:|---:|---:|---:|---:|
| One-shot, local | 9 | 6 | 5 | 5 | 14 | **11** |
| One-shot, Haiku | 15 | 5 | 10 | 2 | 25 | **7** |
| Agent, local | 12 | 7 | 4 | 2 | 16 | **9** |
| Agent, Haiku | 17 | 3 | 10 | 3 | 27 | **6** |

A complete answer can still say things its sources don't. Two readers listed every such claim in every complete answer: a rule, number, condition, consequence, exception, scope, procedure or law name that the chunks the answer cites don't state, or state otherwise.

- **Haiku's complete answers carry fewer of them.** One-shot: 79% of complete answers have such a claim on the local model, 28% on Haiku. Agent: 56% and 22%. That isn't because Haiku says less: its complete answers have a median of 135 and 151 words, against 139 and 124.
- **They carry fewer per answer too.** Counting claims in complete answers, reader A and reader B: one-shot 26 and 25 on the local model in 14 answers, 8 and 8 on Haiku in 25. Agent 19 and 19 in 16, 7 and 7 in 27.
- **On test alone the agent doesn't show it.** 3 of 10 on Haiku against 2 of 4 on the local agent is too few to say anything. The one-shot does: 2 of 10 against 5 of 5.
- **The agent's edge here mostly goes.** The local agent had fewer such claims than the local one-shot, 9 of 16 against 11 of 14, perhaps because its Judge shows the Writer fewer chunks. With Haiku the two are close, 6 of 27 against 7 of 25.
- **Most of Haiku's are labels and scopes, not rules.** It calls an act a national collective agreement, or says a rule is about ΚΤΕΛ, where the chunk doesn't say so. Not all are harmless. `single-06` on one-shot Haiku says an employer who doesn't keep the notice period pays half the compensation. The chunk gives the half when the notice period is kept. No count here weighs how much a claim matters.

Anyone relying on these answers should still check the source. Every claim from both readers, on all five systems, is in [`eval/hand_read.json`](../eval/hand_read.json). These are Haiku's, on the complete answers:

| System | Set | Question | What its sources don't support |
|---|---|---|---|
| One-shot Haiku | dev | `single-14` | It says hours from 41 to 48 «πληρώνονται ως υπερωρία», whereas glc-22329-002 calls this «υπερεργασία» with a «συμπληρωματική αμοιβή». |
| One-shot Haiku | dev | `single-15` | The label «Εθνική Γενική Συλλογική Σύμβαση Εργασίας 1989» for Υ.Α. 12756/1989 is not in the cited chunk. |
| One-shot Haiku | dev | `single-26` | The detail «την τελευταία ή προτελευταία Κυριακή του έτους» for Β.Δ. 750/1971 is not in the cited chunk, which only refers to art. 1. |
| One-shot Haiku | dev | `single-27` | The group «εργάτες που μετανάστευσαν στο Βέλγιο για ανθρακωρυχεία» is not in the cited chunk, which says only «Ο εργάτης». |
| One-shot Haiku | dev | `single-32` | The label «των ΚΤΕΛ» is not in the cited chunk, which says only «προσωπικού κινήσεως». |
| One-shot Haiku | test | `sector-04` | It says Π.Δ. 119/1973 "ισχύει για το προσωπικό κίνησης των υπεραστικών ΚΤΕΛ"; the cited chunk does not state that scope. It says "Το Π.Δ. 288/1976 αφορά μόνο τα αστικά ΚΤΕΛ"; the cited chunk does not mention urban ΚΤΕΛ. |
| One-shot Haiku | test | `single-06` | It says an employer who does not keep the period pays "το ήμισυ της αποζημίωσης"; the chunk gives the half when the employer does give the notice period, the opposite case. |
| Agent Haiku | dev | `single-26` | The explanation that the Sundays of Β.Δ. 750/1971 are «την τελευταία ή προτελευταία Κυριακή κάθε έτους» is not in the cited chunk, which only refers to art. 1. |
| Agent Haiku | dev | `single-32` | The description of the source as «υπουργική απόφαση για τον καθορισμό κατώτατων μισθών και ημερομισθίων» is not in the cited chunk. |
| Agent Haiku | dev | `vocab-03` | The limit to «μικρά αρτοποιεία» is not in art. 9, which is defined by products and indirectly heated ovens, not size. |
| Agent Haiku | test | `lookup-04` | It says the article belongs to "ελάχιστες προδιαγραφές" for working time "σε συμμόρφωση με την οδηγία 93/104/ΕΚ"; the cited chunk mentions neither. |
| Agent Haiku | test | `sector-04` | It says the rule of Π.Δ. 119/1973 "αφορά ειδικά το προσωπικό των ΚΤΕΛ"; the cited chunk does not name ΚΤΕΛ. |
| Agent Haiku | test | `sector-06` | It says the extra leave is "όχι για όλους τους εργαζόμενους με αναπηρία", though the chunk does not say who par. 4 leaves out and the answer admits it can't tell who is covered. (one reader only) |
| Agent Haiku | test | `single-31` | It calls Υ.Α. 11753/1990 a "δημοσίευση της Εθνικής ΓΣΣΕ 1990"; the cited chunk does not mention that agreement. |

## What it shows

- **The Writer was the weak step.** Phase 4A pointed there, and changing it doubles complete answers on test. The right chunk reaches the Writer about as often as before (15 and 16 of 17, against 15 and 14), so the gain is in what happens after search. Writer failures on test fall from 13 to 5 on the one-shot, and from 10 to 6 on the agent, whose Judge failures fall from 3 to 0.
- **Better search alone didn't do this.** One-shot v2 reaches the right chunk for 15 of 17 on test, against 12 on the baseline, and complete answers stay at 5.
- **Refusals improve too.** On test, 4 of 4 on both Haiku systems, against 1 and 3, with prompts written for the local model.
- **One-shot Haiku's wrong refusals come when search fails.** All 4 of them, `single-09`, `vocab-01` and `lookup-01` on dev and `lookup-04` on test, are on questions where the right chunk isn't among its 8. On those three dev questions, the local one-shot writes an answer anyway.
- **With Haiku, the agent earns less.** Complete answers are 10 against 10 on test and 17 against 15 on dev. It takes about twice as long and costs about twice as much. What it buys is a little more reach, the right chunk for 25 against 22 on dev and 16 against 15 on test, and no wrong refusals where one-shot Haiku has 4. Whether that's worth it depends on what a wrong refusal costs you.
- **Haiku is faster here, and costs little.** The median question takes 10 s and 21 s on test, against 49 s and 118 s on the local model. That's one laptop against a paid service, so it says nothing about other machines.
- **The local agent's lead on dev still didn't carry over.** It leads the local one-shot 12 to 9 on dev, and trails it 4 to 5 on test. That's a gap of one answer on test, but dev isn't a fair place for it: its rules were built while reading those answers.

## Does the Judge need to be Haiku?

`agent-mixed` is the agent with a local Judge and a Haiku Writer, and nothing else changed. It ran on the dev questions only and doesn't touch test, so it's a diagnostic and not a result like the five above. Two more fresh readers read its complete answers blind, shuffled with 41 answers already read. They differed once, on the local agent's `single-23`, which I ruled a fail as before. Otherwise, on those 41, they matched every stored verdict and every flag of an unsupported claim. That shows how consistent one model is with itself, not that its readers are independent.

| Dev | Agent | Agent-mixed | Agent Haiku | One-shot Haiku |
|---|---:|---:|---:|---:|
| Judge | local | local | Haiku | none |
| Writer | local | Haiku | Haiku | Haiku |
| **Complete answers, read by hand** | **12 of 26** | **17 of 26** | **17 of 26** | **15 of 26** |
| Of those, with a claim their sources don't support | 7 | 3 | 3 | 5 |
| Wrong refusals | 1 of 26 | 2 of 26 | 0 of 26 | 3 of 26 |
| Correct refusals | 5 of 6 | 5 of 6 | 5 of 6 | 5 of 6 |
| Right chunk reached the Writer | 24 of 27 | 24 of 27 | 25 of 27 | 22 of 27 |
| Questions using 1 / 2 / 3 rounds | 26 / 4 / 2 | 26 / 4 / 2 | 28 / 3 / 1 | - |
| Time per question (median) | 141 s | 76 s | 20 s | 12 s |
| Time for the whole run | 94 min | 58 min | 11 min | 6 min |
| Cost of the whole run | $0.00 | $0.05 | $0.13 | $0.08 |

**On these questions, not for complete answers or unsupported claims.** With a local Judge and a Haiku Writer, the agent has 17 complete answers, 3 of them with an unsupported claim, the same counts as agent Haiku. Question by question it's 3 each way, so the two can't be told apart. But the local Judge doesn't give all of the agent's value.

- **The Writer is the whole gain from the local agent to agent-mixed.** The local Judge made the same decisions and approved the same chunks in both runs, on all 32 questions, so the same chunks reached both Writers. Complete answers go from 12 to 17: 7 questions complete only with Haiku writing, and 2 only with the local Writer.
- **Searching again: the local Judge does it, and more than Haiku's.** It uses extra rounds on 6 questions, Haiku's on 4. Both find the right chunk in round 2 on `single-09`. Haiku's also finds it on `lookup-01`. The code's stop rule fired 5 times on the local Judge and never on Haiku's, because Haiku's Judge stops searching by itself.
- **No wrong refusals: the local Judge doesn't give that.** It has 2 against 0, but only one is a real difference. On `lookup-01`, Haiku's Judge approves a chunk from the right law as partly relevant, and the agent's rule of reading the articles next to an approved chunk finds the right one. The local Judge approves nothing from that law, so that rule never fires, and it refuses after 3 rounds. On `vocab-01` the right chunk reaches no one. The Haiku Writer says it found nothing after the local Judge, while agent Haiku writes an answer with none of the key facts, and that isn't clearly better.
- **What Haiku's Judge buys is speed.** The median question takes 20 s against 76 s, and the whole run 11 minutes against 58. The local Judge is 88% of agent-mixed's time, and it saves only about $0.08 per run, so for a demo agent Haiku is the better choice.
- **Against one-shot Haiku, the local Judge keeps part of the agent's value.** 17 complete answers against 15, the right chunk for 24 against 22, and 2 wrong refusals against 3.

**Why not to lean on this.** It's one run on 26 questions that can be answered. The agent's rules, among them the stop rule and the reading further in round 2, were built on dev with this same local Judge, so dev flatters it. The stored test runs hint the other way: there the local Judge refused `single-25` and `vocab-04` with the right chunk in places 1 and 2, and Haiku's Judge refused neither. Agent-mixed didn't run on test, so what it would do there isn't known.

## The overtime question

`reference-01` asks a factory worker's rate for overtime. The right answer says the general rate is in article 1 of Ν. 435/1976, and that its text isn't in our data. All five systems answer instead, so all five fail it.

**Does Haiku tell υπερεργασία from υπερωρία? No.** Both Haiku systems cite Υ.Α. 11282/1979 art. 7, headed «Αμοιβή υπερεργασίας», and give its 25% as the answer to a question about υπερωρίες, without saying the two differ. One-shot Haiku uses the word υπερωρίες only in a line on night and Sunday work. Agent Haiku never uses it. Neither names Ν. 435/1976.

The local systems make the same mistake, so this is no worse than before. It isn't all the Writer's fault either: on all five, the four chunks that point to Ν. 435/1976 stay at places 15 and 27 of the search and never reach it. Two small gains: one-shot Haiku says the ΚΤΕΛ rates aren't general, and agent Haiku gives the textile and furniture rates as conditions and not as the rule.

The same confusion shows elsewhere. On `single-14`, one-shot Haiku's answer passes, but says the hours from 41 to 48 «πληρώνονται ως υπερωρία», where its chunk calls them υπερεργασία. Agent Haiku on the same question gives υπερεργασία as the reason for an overtime limit. In our texts they are different things, with their own rates and limits. Haiku doesn't work that out from these chunks.

## Cost and time per run

| System | Set | Questions | Calls to Haiku | Tokens in | Tokens out | Of those, thinking | Cost of the run | Per question | Whole run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| One-shot Haiku | dev | 32 | 32 | 312,522 | 87,645 | 75% | $0.0751 | $0.0023 | 6.2 min |
| One-shot Haiku | test | 20 | 20 | 197,853 | 47,873 | 73% | $0.0437 | $0.0022 | 3.5 min |
| Agent Haiku | dev | 32 | 64 | 558,725 | 147,855 | 64% | $0.1298 | $0.0041 | 11.4 min |
| Agent Haiku | test | 20 | 44 | 413,650 | 100,863 | 62% | $0.0918 | $0.0046 | 8.0 min |
| Agent-mixed (local Judge) | dev | 32 | 27 | 160,138 | 74,652 | 75% | $0.0533 | $0.0017 | 57.7 min |

Everything spent on measuring in Phase 4B, with the key check and three trial questions, comes to **$0.41** of the $3 limit. That counts the calls to Haiku, not the work of reading the answers. Haiku's thinking is most of its output and is billed as output, which is why a call costs about $0.002 and not the fraction of that the visible answer would suggest. In the agent's Haiku test run, the Judge takes 55% of the time, the Writer 36% and the local Query Enhancer 7%. The local systems cost no money here, but they tie up the machine: 52 minutes for the agent's test run.

## How little this can show

**20 test questions is few.** 16 can be answered, so one answer is about 6 points. 4 must be refused, so one refusal is 25 points.

Taking the same questions one by one, and leaving out those where both are complete or neither is:

| Compared | Set | Complete only on the first | Complete only on the second | Chance of a split this uneven if they were equally good |
|---|---|---:|---:|---:|
| One-shot Haiku against One-shot v2 | test | 5 | 0 | 0.06 |
| Agent Haiku against Agent | test | 6 | 0 | 0.03 |
| Agent Haiku against One-shot Haiku | test | 1 | 1 | 1.00 |
| Agent against One-shot v2 | test | 2 | 3 | 1.00 |
| Agent against Baseline | test | 2 | 3 | 1.00 |
| One-shot v2 against Baseline | test | 1 | 1 | 1.00 |
| One-shot Haiku against One-shot v2 | dev | 7 | 1 | 0.07 |
| Agent Haiku against Agent | dev | 6 | 1 | 0.12 |
| Agent Haiku against One-shot Haiku | dev | 4 | 2 | 0.69 |
| Agent against One-shot v2 | dev | 5 | 2 | 0.45 |
| Agent against Baseline | dev | 8 | 2 | 0.11 |
| One-shot v2 against Baseline | dev | 5 | 2 | 0.45 |

Only agent Haiku against the local agent on test falls below 0.05, at 0.03, and one-shot Haiku against the local one-shot comes close, at 0.06. With 12 comparisons, one like that could turn up by chance. What gives them more weight is that all four comparisons of Haiku with the local model point the same way: 24 questions complete only on Haiku, 2 only on the local model. They share questions and a Writer, so that isn't 26 separate results. Neither Haiku system can be told from the other, and no two local systems can be told apart on test.

- **The test set is small, and it has been read.** The complete local answers were read in Phase 4A, before these runs. Nothing was changed because of that: Haiku uses the same prompts, and its code was frozen before its first dev run. A larger fresh test set is a later option.
- **Test looks easier than dev.** The same baseline has 23% of answers complete on dev and 31% on test, and the right chunk reaches its Writer for 48% and 71%. Compare systems within a set, not across sets.
- **Dev doesn't lean towards Haiku.** The agent's rules were built on dev with the local model, and Haiku got no tuning at all. If dev leans either way, it leans against Haiku.
- **Runs aren't exactly repeatable.** Haiku takes no seed, so another run could give other answers. One run each is what we have. In Phase 3C.1, two small fixes changed 6 of 32 answers.
- **Two readers, no lawyer, and they aren't independent.** Two fresh Claude agents read all 111 answers with the labels hidden and the answers to each question shuffled. They agreed on 109. That high agreement isn't proof, because they're the same model. Haiku is a Claude model too, so they may favour its style, and hidden labels don't hide a style: a reader can tell two kinds of writing apart. The local answers do read differently. This is the largest doubt in this report, and only a human reader could remove it.
- **Where the readers differed, I ruled.** On v2's `single-23` I failed it, because "only for fines" misstates the closed list. On one-shot Haiku's `single-04` I failed it, because the "only" in the key fact isn't there. That one is the closest call in the read. I could work out that it was Haiku's, so I took the stricter side. If it passed, one-shot Haiku would have 11 on test.
- **The blind read changed earlier verdicts.** Both readers pass the baseline's `sector-03` and v2's `single-27`, which I failed in Phase 4A: their mistakes are outside the key facts, and `single-27`'s own notes say the date isn't asked for. Both are listed as unsupported claims. Both readers also fail `single-23` on the three local systems, which I passed. So dev moves: the agent from 13 to 12, with v2 at 9 and the baseline at 6 for different answers than before. Every test verdict from Phase 4A stood.
- **Hand reading only takes away.** Answers scored incomplete weren't read on test. The matcher was tuned on local answers, so it may miss right answers from any system, and more from one than another.
- **Unsupported claims are counted among complete answers only,** against the chunks each answer cites. Answers that fail aren't in those counts.
- **I wrote the test set.** The owner reviewed 20 of its 52 items. Its expected answers follow our 1852-1999 data, not today's law.

## Failures by step

Test answers are listed by id only. Those scored incomplete weren't read.

| System | Set | Search | Judge | Writer |
|---|---|---|---|---|
| Baseline | dev | 13: `lookup-01`, `reference-02`, `sector-05`, `single-09`, `single-10`, `single-14`, `single-17`, `single-21`, `single-29`, `vocab-01`, `vocab-02`, `vocab-03`, `vocab-06` | - | 9: `lookup-03`, `reference-01`, `refuse-06`, `sector-01`, `sector-02`, `single-02`, `single-18`, `single-23`, `single-32` |
| One-shot v2 | dev | 4: `lookup-01`, `sector-05`, `single-09`, `vocab-01` | - | 15: `lookup-03`, `reference-01`, `reference-02`, `refuse-06`, `sector-01`, `sector-03`, `single-10`, `single-11`, `single-14`, `single-17`, `single-18`, `single-23`, `vocab-02`, `vocab-03`, `vocab-06` |
| Agent | dev | 2: `lookup-01`, `vocab-01` | 1: `reference-01` | 12: `reference-02`, `sector-01`, `sector-02`, `sector-03`, `single-01`, `single-09`, `single-10`, `single-14`, `single-23`, `vocab-02`, `vocab-03`, `vocab-06` |
| One-shot Haiku | dev | 4: `lookup-01`, `sector-05`, `single-09`, `vocab-01` | - | 8: `reference-01`, `reference-02`, `sector-03`, `single-02`, `single-10`, `single-11`, `vocab-02`, `vocab-06` |
| Agent Haiku | dev | 1: `vocab-01` | 1: `reference-01` | 8: `reference-02`, `sector-03`, `single-01`, `single-02`, `single-10`, `single-14`, `vocab-02`, `vocab-06` |
| Baseline | test | 5: `lookup-02`, `sector-04`, `single-03`, `single-25`, `vocab-04` | - | 8: `reference-03`, `refuse-05`, `sector-06`, `single-04`, `single-05`, `single-08`, `single-12`, `single-19` |
| One-shot v2 | test | 1: `lookup-04` | - | 13: `reference-03`, `refuse-02`, `refuse-05`, `sector-04`, `sector-06`, `single-03`, `single-04`, `single-05`, `single-08`, `single-12`, `single-19`, `single-25`, `vocab-04` |
| Agent | test | 0 | 3: `reference-03`, `single-25`, `vocab-04` | 10: `sector-04`, `sector-06`, `single-03`, `single-04`, `single-05`, `single-06`, `single-08`, `single-19`, `single-22`, `single-31` |
| One-shot Haiku | test | 1: `lookup-04` | - | 5: `single-03`, `single-04`, `single-05`, `single-19`, `single-25` |
| Agent Haiku | test | 0 | 0 | 6: `single-03`, `single-04`, `single-05`, `single-08`, `single-19`, `single-25` |

## Answers scored complete that fail when read

| System | Set | Question | Why it fails |
|---|---|---|---|
| Baseline | dev | `lookup-03` | It says the law makes 1 May a holiday. The law says it can be made one by a minister's decision, each year. |
| Baseline | dev | `sector-02` | Its short answer allows overtime «πέραν των 120 ωρών ετησίως». The limit is at most 120 hours a year. |
| Baseline | dev | `single-23` | It speaks only of fines, and never says that deductions in general are allowed only in the cases the law lists. |
| One-shot v2 | dev | `lookup-01` | "Subject to article 3" isn't there: the matcher took a list number "3." for it. The right chunk wasn't among its 8, so this counts as a search failure. |
| One-shot v2 | dev | `single-17` | Its short answer turns the exception around: dismissal depends on how long a health stoppage lasts. The key fact is a serious reason, given in writing. |
| One-shot v2 | dev | `single-23` | It says the law allows deductions «μόνο για πρόστιμα». The chunk lists seven kinds, so the closed list is stated wrong. The readers differed, and I ruled. |
| Agent | dev | `sector-01` | It says 5 days for six years of service. The chunk says 30. |
| Agent | dev | `sector-02` | It says «δεν απαιτεί προηγούμενη άδεια». The chunk says «μόνον κατόπιν αδείας». |
| Agent | dev | `single-10` | It starts the six months from the payment. The chunk says «αφ' ης κατέστη απαιτητή». |
| Agent | dev | `single-23` | It speaks only of fines, and never says that deductions in general are allowed only in the cases the law lists. |
| One-shot Haiku | dev | `single-11` | It never says the reasons must not concern the person dismissed. The only similar word is «προσωπικό», meaning the staff count. |
| Agent Haiku | dev | `single-02` | It never says the increased pay is due at the end of the year. «πριν λήξει το έτος» is the deadline for granting the leave. |
| Baseline | test | `single-08` | The key fact names four years of service. The answer never says that, and says the law protects those with «περισσότερους από τέσσερις μήνες». |
| Baseline | test | `single-12` | It says the 24 hours end at 24:00 «της επόμενης ημέρας». The chunk has them start at 00:01 and end at 24:00 the same day. |
| One-shot v2 | test | `single-25` | Its short answer opens with «Δεν χρειάζεται αποζημίωση» for a week away, unless the stoppage is over four days. A week is over four days, so the rule gives this person the opposite. |
| Agent | test | `single-08` | It never says the illness must be proved. Its short answer skips those words with "…", and the matcher took «αποδεικνύει εγκατάλειψη», about something else, for that fact. |
| One-shot Haiku | test | `single-04` | The key fact says money replaces leave only when employment ends. The answer says money is due then, never says only, and lists a second route to money. The readers differed, and I ruled: the closest call in the read. |
| Agent Haiku | test | `single-08` | It invents an absence of two months, «η διάρκεια των δύο μηνών σας βρίσκεται πέρα από το όριο του ενός μήνα». The person was away one month, so the rule comes out reversed for them. |

## How the runs were made

- **The guard.** `labour_rag/evaluate.py` lets each named system use the test split once, and only with its own settings. A Haiku system must also have finished the dev questions first.
- **The freeze.** The Haiku code is new files next to the frozen code. The one change to frozen files is the `--haiku` flag, in the `main()` of `ask.py` and `agent.py`. It came after the runs of the five systems and before `agent-mixed`'s, and it doesn't touch what decides an answer. `evaluate` compares those two files without their `main()`, and everything else with `git diff --diff-filter=a`, against both `agent-frozen-3c1` and `haiku-frozen-4b`, the tag set before Haiku's first dev run. Nothing else has changed since either tag.
- **The budget guard.** $1 per run and $3 across all of 4B, in `labour_rag/budget.py`, on top of a $10 monthly limit on the workspace. It counts real usage after every call, keeps the total on disk in [`eval/haiku_spend.json`](../eval/haiku_spend.json), and doesn't make a call that could pass a limit. It never had to stop anything. Manual `--haiku` runs have their own record and $2 limit, in the gitignored `data/haiku_manual_spend.json`.
- **The key.** The code reads it only to hand it to the SDK. I never saw it: it wasn't opened by hand, printed or logged. One tiny call first confirmed it worked, for $0.000004. Since then, every Haiku run checks it before any search, with a call that uses no tokens.
- **The runs.** Haiku's and `agent-mixed` ran on 2026-11-06, detached from the session, one after the other, with no other model job, and each answered every question. The local test runs are from 2026-11-05, and the baseline's from 2026-11-04.
- **Two corrections.** The Phase 3C report said 15 complete answers against 12 on dev. Phase 4A made that 13 against 9. The blind read makes it 12 against 9. [The agent report](agent-report.md) is corrected.

## What comes next

The most useful next step is a larger fresh test set, read by a person. It's the one thing that can settle what these numbers only suggest, and it would also show whether a human reader sees what two Claude readers saw. After that comes Phase 5, the modern layer.
