"""Phases 4A and 4B: write docs/final-report.md from the stored runs. Needs no database and no model. agent-mixed is a dev-only diagnostic beside the five systems.

    .venv/bin/python -m labour_rag.evaluate --split test --system oneshot-v2
    .venv/bin/python -m labour_rag.evaluate --split test --system agent --name agent-3c1-qwen3-4b-semantic-units-limit4-test
    .venv/bin/python -m labour_rag.evaluate --split dev --system oneshot-haiku      # then --split test, and the same for agent-haiku
    .venv/bin/python -I scripts/final_report.py

Each test run can be made once. The verdicts are in eval/hand_read.json, from two blind readers of every answer scored complete. The words around
the numbers are hand-written (SHORT_VERSION, SYSTEMS_TEXT, TABLE_NOTES, UNSUPPORTED_TEXT, SHOWS, JUDGE_TEXT, OVERTIME, LIMITS, HOW_RUN, NEXT), and so is EVIDENCE:
the script stops if the claims it can check stop holding, and all of it must be redone whenever the runs or the verdicts change. It also stops if
the tables in README.md differ from the ones here.
"""

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag.evaluate import TEST_SETTINGS, agent_problem, problem  # noqa: E402
from scripts.eval_report import find_run  # noqa: E402
from scripts.retrieval_report import chance_of_split  # noqa: E402

REPORT = ROOT / "docs/final-report.md"
README = ROOT / "README.md"
TEST_RUNS = ROOT / "eval/test_runs.json"
HAND_READ = ROOT / "eval/hand_read.json"
LEDGER = ROOT / "eval/haiku_spend.json"

SPLITS = ("dev", "test")
SYSTEMS = {"baseline": "Baseline", "oneshot-v2": "One-shot v2", "agent": "Agent", "oneshot-haiku": "One-shot Haiku", "agent-haiku": "Agent Haiku"}
HAIKU = ("oneshot-haiku", "agent-haiku")
MIXED = "agent-mixed"       # local Judge, Haiku Writer, dev only
MIXED_RUN = "agent-mixed-qwen3-4b-semantic-units-limit4-dev"
AGENTS = ("agent", "agent-haiku", MIXED)
PAIRS = (("oneshot-haiku", "oneshot-v2"), ("agent-haiku", "agent"), ("agent-haiku", "oneshot-haiku"), ("agent", "oneshot-v2"), ("agent", "baseline"), ("oneshot-v2", "baseline"))
RUNS = {("baseline", "dev"): "oneshot-limit2-dev",
        ("baseline", "test"): "oneshot-limit2-test",
        ("oneshot-v2", "dev"): "oneshot-qwen3-4b-semantic-units-limit2-dev",
        ("oneshot-v2", "test"): "oneshot-qwen3-4b-semantic-units-limit2-test",
        ("agent", "dev"): "agent-3c1-qwen3-4b-semantic-units-limit4-dev",
        ("agent", "test"): "agent-3c1-qwen3-4b-semantic-units-limit4-test",
        ("oneshot-haiku", "dev"): "oneshot-haiku-qwen3-4b-semantic-units-limit2-dev",
        ("oneshot-haiku", "test"): "oneshot-haiku-qwen3-4b-semantic-units-limit2-test",
        ("agent-haiku", "dev"): "agent-haiku-qwen3-4b-semantic-units-limit4-dev",
        ("agent-haiku", "test"): "agent-haiku-qwen3-4b-semantic-units-limit4-test"}

READ = json.loads(HAND_READ.read_text(encoding="utf-8"))
# Scored as complete, but wrong when read. The rule, for all systems: an answer fails if it states a key fact wrong or leaves one out, anywhere,
# short answer included. Errors outside the key facts are listed as unsupported claims, and don't fail it.
WRONG_THOUGH_COMPLETE = {(system, split): {item: entry["why"] for item, entry in READ[split].get(system, {}).items() if entry["verdict"] == "fail"}
                         for split in SPLITS for system in (*SYSTEMS, MIXED)}

# What each fail rests on: words that must be in the answer, and words that must not.
EVIDENCE = {
    ("baseline", "dev", "lookup-03"): (["καθιερώνεται η 1η Μαΐου"], ["κάθε χρόνο", "κάθε έτος", "ετησίως"]),
    ("baseline", "dev", "sector-02"): (["πέραν των 120 ωρών"], []),
    ("baseline", "dev", "single-23"): (["δεν επιτρέπεται να κρατάται πρόστιμο"], []),
    ("oneshot-v2", "dev", "lookup-01"): ([], ["επιφύλαξη"]),
    ("oneshot-v2", "dev", "single-17"): (["δεν υπερβαίνει το ανώτατο χρονικό διάστημα"], []),
    ("oneshot-v2", "dev", "single-23"): (["μόνο για πρόστιμα"], []),
    ("agent", "dev", "single-10"): (["έγινε η καταβολή της αποζημίωσης"], []),
    ("agent", "dev", "sector-01"): (["πέντε τουλάχιστον ημέρας"], []),
    ("agent", "dev", "sector-02"): (["δεν απαιτεί προηγούμενη άδεια"], []),
    ("agent", "dev", "single-23"): (["η κράτηση προστίμου"], []),
    ("oneshot-haiku", "dev", "single-11"): ([], ["πρόσωπ", "προσώπ"]),
    ("agent-haiku", "dev", "single-02"): (["πριν λήξει το έτος"], ["με τη λήξη", "λήξη του έτους"]),
    ("baseline", "test", "single-08"): (["περισσότερους από τέσσερις μήνες"], ["τέσσερα χρόνια", "τεσσάρων ετών", "τετραετ"]),
    ("baseline", "test", "single-12"): (["της επόμενης ημέρας"], []),
    ("oneshot-v2", "test", "single-25"): (["Δεν χρειάζεται αποζημίωση"], []),
    ("agent", "test", "single-08"): (["αποδεικνύει εγκατάλειψη"], ["αποδείξ", "αποδεδειγμέν"]),
    ("oneshot-haiku", "test", "single-04"): (["Αν λυθεί η σχέση εργασίας", "αυξημένες κατά 100%"], ["μόνο όταν", "μόνον σε περίπτωση"]),
    ("agent-haiku", "test", "single-08"): (["των δύο μηνών σας"], []),
}

SHORT_VERSION = """**In short.** Replacing the local Judge and Writer with Claude Haiku is the first change in this project that shows up in complete answers on the test questions. Read by hand, complete answers on test go from 5 to \
10 of 16 for the one-shot, and from 4 to 10 for the agent. On dev they go from 9 to 15 of 26, and from 12 to 17. Haiku's complete answers also say less that their sources don't support: on both sets together, 7 of 25 \
against 11 of 14 for the one-shot, and 6 of 27 against 9 of 16 for the agent. A full test run cost $0.04 and $0.09, and took less time than the local ones. With Haiku writing, the agent adds little to complete answers \
(10 against 10 on test, 17 against 15 on dev), but it makes no wrong refusals where one-shot Haiku makes 4. A dev-only diagnostic says the Judge needn't be Haiku for complete answers, but Haiku's Judge is about 4 times faster ([details](#does-the-judge-need-to-be-haiku)). These sets are still small, the test questions have been read before, and the readers are Claude models judging a \
Claude model: see [How little this can show](#how-little-this-can-show)."""

SYSTEMS_TEXT = """| System | How it answers | Search | Judge and Writer |
|---|---|---|---|
| Baseline | Searches once and answers | bge-m3, semantic and keyword search mixed by equal-weight RRF, at most 2 chunks per act, the old repeat filter | `ministral-3:8b`, local |
| One-shot v2 | Searches once and answers | qwen3-embedding:4b, semantic only, at most 2 chunks per act, repeats judged by numbers with a unit | `ministral-3:8b`, local |
| Agent | Search, Judge, up to 3 rounds, Writer, citation check | The same as v2 with at most 4 chunks per act, frozen at the tag `agent-frozen-3c1` | `ministral-3:8b`, local |
| One-shot Haiku | The same as one-shot v2 | The same as one-shot v2 | `claude-haiku-5-5`, cloud |
| Agent Haiku | The same as the agent | The same as the agent | `claude-haiku-5-5`, cloud |

All five use the same prompts. The local model runs at temperature 0.2 or 0 with a fixed seed. Haiku runs at its defaults: no temperature, no seed, thinking at its default effort. So it isn't only the model that changes, and Haiku's runs \
aren't exactly repeatable. **With Haiku, the question and the law chunks leave the machine.** The chunks are public law texts. Search, embeddings and the Query Enhancer stay local on every system."""

TABLE_NOTES = """- **Complete answers, read by hand.** The matcher looks for every key fact, but it can't read meaning. So every answer it scored complete was read, and those that state a key fact wrong or leave one out were taken away, short answer included. \
Answers it scored incomplete weren't read on test, so its misses stay as failures on every system.
- **With a claim their sources don't support.** Among the complete answers: those with a side claim the chunks they cite don't support, as listed by both readers. One reader alone adds one more, on one-shot v2 on dev and on agent Haiku on test. [The next section](#unsupported-claims-local-against-haiku) has more.
- **Right chunk reached the Writer.** The chunk that holds the answer was among those the Writer received.
- **Time** is from one run on one laptop. Haiku's includes the network. The baseline's runs are from an earlier day, and Phase 2 already noted that their times are weak. **Cost** is real usage, counted after every call. Local models cost no money here.
- **Failures** add up to the questions minus complete answers and correct refusals. *Search:* the right chunk never reached the Writer (one-shots) or the Judge (agents). *Judge:* it held back the right chunk, or let through a question that should have been refused. \
*Writer:* it had the right chunk and still fell short. One-shots have no Judge, so answering a question that should have been refused counts as the Writer's."""

UNSUPPORTED_TEXT = """A complete answer can still say things its sources don't. Two readers listed every such claim in every complete answer: a rule, number, condition, consequence, exception, scope, procedure or law name that the chunks the answer cites don't state, or state otherwise.

- **Haiku's complete answers carry fewer of them.** One-shot: {oneshot_local:.0%} of complete answers have such a claim on the local model, {oneshot_haiku:.0%} on Haiku. Agent: {agent_local:.0%} and {agent_haiku:.0%}. That isn't because Haiku says less: its complete answers have a median of {words[oneshot-haiku]:.0f} and {words[agent-haiku]:.0f} words, against {words[oneshot-v2]:.0f} and {words[agent]:.0f}.
- **They carry fewer per answer too.** Counting claims in complete answers, reader A and reader B: one-shot {claims[oneshot-v2][0]} and {claims[oneshot-v2][1]} on the local model in {complete[oneshot-v2]} answers, {claims[oneshot-haiku][0]} and {claims[oneshot-haiku][1]} on Haiku in {complete[oneshot-haiku]}. Agent {claims[agent][0]} and {claims[agent][1]} in {complete[agent]}, {claims[agent-haiku][0]} and {claims[agent-haiku][1]} in {complete[agent-haiku]}.
- **On test alone the agent doesn't show it.** 3 of 10 on Haiku against 2 of 4 on the local agent is too few to say anything. The one-shot does: 2 of 10 against 5 of 5.
- **The agent's edge here mostly goes.** The local agent had fewer such claims than the local one-shot, 9 of 16 against 11 of 14, perhaps because its Judge shows the Writer fewer chunks. With Haiku the two are close, 6 of 27 against 7 of 25.
- **Most of Haiku's are labels and scopes, not rules.** It calls an act a national collective agreement, or says a rule is about ΚΤΕΛ, where the chunk doesn't say so. Not all are harmless. `single-06` on one-shot Haiku says an employer who doesn't keep the notice period pays half the compensation. The chunk gives the half when the notice period is kept. No count here weighs how much a claim matters.

Anyone relying on these answers should still check the source. Every claim from both readers, on all five systems, is in [`eval/hand_read.json`](../eval/hand_read.json). These are Haiku's, on the complete answers:"""

SHOWS = """- **The Writer was the weak step.** Phase 4A pointed there, and changing it doubles complete answers on test. The right chunk reaches the Writer about as often as before (15 and 16 of 17, against 15 and 14), so the gain is in what happens after search. Writer failures on test fall from 13 to 5 on the one-shot, and from 10 to 6 on the agent, whose Judge failures fall from 3 to 0.
- **Better search alone didn't do this.** One-shot v2 reaches the right chunk for 15 of 17 on test, against 12 on the baseline, and complete answers stay at 5.
- **Refusals improve too.** On test, 4 of 4 on both Haiku systems, against 1 and 3, with prompts written for the local model.
- **One-shot Haiku's wrong refusals come when search fails.** All 4 of them, `single-09`, `vocab-01` and `lookup-01` on dev and `lookup-04` on test, are on questions where the right chunk isn't among its 8. On those three dev questions, the local one-shot writes an answer anyway.
- **With Haiku, the agent earns less.** Complete answers are 10 against 10 on test and 17 against 15 on dev. It takes about twice as long and costs about twice as much. What it buys is a little more reach, the right chunk for 25 against 22 on dev and 16 against 15 on test, and no wrong refusals where one-shot Haiku has 4. Whether that's worth it depends on what a wrong refusal costs you.
- **Haiku is faster here, and costs little.** The median question takes {oneshot_seconds:.0f} s and {agent_seconds:.0f} s on test, against 49 s and 118 s on the local model. That's one laptop against a paid service, so it says nothing about other machines.
- **The local agent's lead on dev still didn't carry over.** It leads the local one-shot 12 to 9 on dev, and trails it 4 to 5 on test. That's a gap of one answer on test, but dev isn't a fair place for it: its rules were built while reading those answers."""

JUDGE_TEXT = """**On these questions, not for complete answers or unsupported claims.** With a local Judge and a Haiku Writer, the agent has {mixed_complete} complete answers, {mixed_flagged} of them with an unsupported claim, the same counts as agent Haiku. Question by question it's 3 each way, so the two can't be told apart. But the local Judge doesn't give all of the agent's value.

- **The Writer is the whole gain from the local agent to agent-mixed.** The local Judge made the same decisions and approved the same chunks in both runs, on all 32 questions, so the same chunks reached both Writers. Complete answers go from 12 to 17: 7 questions complete only with Haiku writing, and 2 only with the local Writer.
- **Searching again: the local Judge does it, and more than Haiku's.** It uses extra rounds on 6 questions, Haiku's on 4. Both find the right chunk in round 2 on `single-09`. Haiku's also finds it on `lookup-01`. The code's stop rule fired 5 times on the local Judge and never on Haiku's, because Haiku's Judge stops searching by itself.
- **No wrong refusals: the local Judge doesn't give that.** It has 2 against 0, but only one is a real difference. On `lookup-01`, Haiku's Judge approves a chunk from the right law as partly relevant, and the agent's rule of reading the articles next to an approved chunk finds the right one. The local Judge approves nothing from that law, so that rule never fires, and it refuses after 3 rounds. On `vocab-01` the right chunk reaches no one. The Haiku Writer says it found nothing after the local Judge, while agent Haiku writes an answer with none of the key facts, and that isn't clearly better.
- **What Haiku's Judge buys is speed.** The median question takes 20 s against 76 s, and the whole run 11 minutes against 58. The local Judge is {judge_share:.0%} of agent-mixed's time, and it saves only about $0.08 per run, so for a demo agent Haiku is the better choice.
- **Against one-shot Haiku, the local Judge keeps part of the agent's value.** 17 complete answers against 15, the right chunk for 24 against 22, and 2 wrong refusals against 3.

**Why not to lean on this.** It's one run on 26 questions that can be answered. The agent's rules, among them the stop rule and the reading further in round 2, were built on dev with this same local Judge, so dev flatters it. The stored test runs hint the other way: there the local Judge refused `single-25` and `vocab-04` with the right chunk in places 1 and 2, and Haiku's Judge refused neither. Agent-mixed didn't run on test, so what it would do there isn't known."""

OVERTIME = """`reference-01` asks a factory worker's rate for overtime. The right answer says the general rate is in article 1 of Ν. 435/1976, and that its text isn't in our data. All five systems answer instead, so all five fail it.

**Does Haiku tell υπερεργασία from υπερωρία? No.** Both Haiku systems cite Υ.Α. 11282/1979 art. 7, headed «Αμοιβή υπερεργασίας», and give its 25% as the answer to a question about υπερωρίες, without saying the two differ. One-shot Haiku uses the word υπερωρίες only in a line on night and Sunday work. Agent Haiku never uses it. Neither names Ν. 435/1976.

The local systems make the same mistake, so this is no worse than before. It isn't all the Writer's fault either: on all five, the four chunks that point to Ν. 435/1976 stay at places 15 and 27 of the search and never reach it. Two small gains: one-shot Haiku says the ΚΤΕΛ rates aren't general, and agent Haiku gives the textile and furniture rates as conditions and not as the rule.

The same confusion shows elsewhere. On `single-14`, one-shot Haiku's answer passes, but says the hours from 41 to 48 «πληρώνονται ως υπερωρία», where its chunk calls them υπερεργασία. Agent Haiku on the same question gives υπερεργασία as the reason for an overtime limit. In our texts they are different things, with their own rates and limits. Haiku doesn't work that out from these chunks."""

LIMITS = """- **The test set is small, and it has been read.** The complete local answers were read in Phase 4A, before these runs. Nothing was changed because of that: Haiku uses the same prompts, and its code was frozen before its first dev run. A larger fresh test set is a later option.
- **Test looks easier than dev.** The same baseline has 23% of answers complete on dev and 31% on test, and the right chunk reaches its Writer for 48% and 71%. Compare systems within a set, not across sets.
- **Dev doesn't lean towards Haiku.** The agent's rules were built on dev with the local model, and Haiku got no tuning at all. If dev leans either way, it leans against Haiku.
- **Runs aren't exactly repeatable.** Haiku takes no seed, so another run could give other answers. One run each is what we have. In Phase 3C.1, two small fixes changed 6 of 32 answers.
- **Two readers, no lawyer, and they aren't independent.** Two fresh Claude agents read all 111 answers with the labels hidden and the answers to each question shuffled. They agreed on {agreed}. That high agreement isn't proof, because they're the same model. Haiku is a Claude model too, so they may favour its style, and hidden labels don't hide a style: a reader can tell two kinds of writing apart. The local answers do read differently. This is the largest doubt in this report, and only a human reader could remove it.
- **Where the readers differed, I ruled.** On v2's `single-23` I failed it, because "only for fines" misstates the closed list. On one-shot Haiku's `single-04` I failed it, because the "only" in the key fact isn't there. That one is the closest call in the read. I could work out that it was Haiku's, so I took the stricter side. If it passed, one-shot Haiku would have 11 on test.
- **The blind read changed earlier verdicts.** Both readers pass the baseline's `sector-03` and v2's `single-27`, which I failed in Phase 4A: their mistakes are outside the key facts, and `single-27`'s own notes say the date isn't asked for. Both are listed as unsupported claims. Both readers also fail `single-23` on the three local systems, which I passed. So dev moves: the agent from 13 to 12, with v2 at 9 and the baseline at 6 for different answers than before. Every test verdict from Phase 4A stood.
- **Hand reading only takes away.** Answers scored incomplete weren't read on test. The matcher was tuned on local answers, so it may miss right answers from any system, and more from one than another.
- **Unsupported claims are counted among complete answers only,** against the chunks each answer cites. Answers that fail aren't in those counts.
- **I wrote the test set.** The owner reviewed 20 of its 52 items. Its expected answers follow our 1852-1999 data, not today's law."""

HOW_RUN = """- **The guard.** `labour_rag/evaluate.py` lets each named system use the test split once, and only with its own settings. A Haiku system must also have finished the dev questions first.
- **The freeze.** The Haiku code is new files next to the frozen code. The one change to frozen files is the `--haiku` flag, in the `main()` of `ask.py` and `agent.py`. It came after the runs of the five systems and before `agent-mixed`'s, and it doesn't touch what decides an answer. `evaluate` compares those two files without their `main()`, and everything else with `git diff --diff-filter=a`, against both `agent-frozen-3c1` and `haiku-frozen-4b`, the tag set before Haiku's first dev run. Nothing else has changed since either tag.
- **The budget guard.** $1 per run and $3 across all of 4B, in `labour_rag/budget.py`, on top of a $10 monthly limit on the workspace. It counts real usage after every call, keeps the total on disk in [`eval/haiku_spend.json`](../eval/haiku_spend.json), and doesn't make a call that could pass a limit. It never had to stop anything. Manual `--haiku` runs have their own record and $2 limit, in the gitignored `data/haiku_manual_spend.json`.
- **The key.** The code reads it only to hand it to the SDK. I never saw it: it wasn't opened by hand, printed or logged. One tiny call first confirmed it worked, for ${key_check:.6f}. Since then, every Haiku run checks it before any search, with a call that uses no tokens.
- **The runs.** Haiku's and `agent-mixed` ran on 2026-11-06, detached from the session, one after the other, with no other model job, and each answered every question. The local test runs are from 2026-11-05, and the baseline's from 2026-11-04.
- **Two corrections.** The Phase 3C report said 15 complete answers against 12 on dev. Phase 4A made that 13 against 9. The blind read makes it 12 against 9. [The agent report](agent-report.md) is corrected."""

EXPECTED_BELOW = {("test", "agent-haiku", "agent")}
PAIRS_TEXT = """Only agent Haiku against the local agent on test falls below 0.05, at 0.03, and one-shot Haiku against the local one-shot comes close, at 0.06. With 12 comparisons, one like that could turn up by chance. What gives them more weight is that all four comparisons of Haiku with the local model point the same way: 24 questions complete only on Haiku, 2 only on the local model. They share questions and a Writer, so that isn't 26 separate results. Neither Haiku system can be told from the other, and no two local systems can be told apart on test."""

NEXT = """The most useful next step is a larger fresh test set, read by a person. It's the one thing that can settle what these numbers only suggest, and it would also show whether a human reader sees what two Claude readers saw. After that comes Phase 6, the modern layer."""


def failure_of(system, record, wrong):
    """Which step an answer fell short at, or None. An answer that fails when read goes through the same functions as one that lacks a key fact."""
    if record["id"] in wrong:
        record = {**record, "score": {**record["score"], "fact_share": 0}}
    step = agent_problem(record) if system in AGENTS else problem(record)
    return "writer" if step == "reading" else step


def numbers(system, run, split, ledger):
    """What the tables say about one system on one set."""
    items = run["items"]
    read = READ[split][system]
    wrong = WRONG_THOUGH_COMPLETE[system, split]
    answerable = [r for r in items.values() if r["answerable"]]
    must_refuse = [r for r in items.values() if not r["answerable"]]
    gold = [r for r in items.values() if r["retrieval"]]
    matched = {r["id"] for r in answerable if r["score"]["fact_share"] == 1 and not r["score"]["refused"]}
    complete = matched - set(wrong)
    failures = {"search": [], "judge": [], "writer": []}
    for record in items.values():
        step = failure_of(system, record, wrong)
        if step:
            failures[step].append(record["id"])
    return {"answerable": len(answerable), "must_refuse": len(must_refuse), "gold": len(gold), "matched": matched, "complete": complete,
            "facts": run["summary"]["overall"]["fact_share"], "correct_refusals": sum(r["score"]["refused"] for r in must_refuse),
            "wrong_refusals": {r["id"] for r in answerable if r["score"]["refused"]}, "reached": sum(bool(r["retrieval"]["in_context"]) for r in gold),
            "seconds": run["summary"]["overall"]["seconds_median"], "minutes": sum(s for r in items.values() for s in r["times"].values()) / 60,
            "failures": failures, "questions": len(items), "has_judge": system in AGENTS,
            "flagged_both": {i for i in complete if read[i]["reader_a"]["unsupported"] and read[i]["reader_b"]["unsupported"]},
            "flagged_either": {i for i in complete if read[i]["reader_a"]["unsupported"] or read[i]["reader_b"]["unsupported"]},
            "claims": (sum(len(read[i]["reader_a"]["unsupported"]) for i in complete), sum(len(read[i]["reader_b"]["unsupported"]) for i in complete)),
            "cost": ledger["runs"].get(run["dir"], {}).get("spent", 0.0), "dir": run["dir"]}


def main_table(n, split):
    """Every system on one set, side by side. README.md carries the same tables."""
    rows = [("**Complete answers, read by hand**", lambda c: f"**{len(c['complete'])} of {c['answerable']}**"),
            ("Of those, with a claim their sources don't support", lambda c: str(len(c["flagged_both"]))),
            ("Complete by the matcher alone", lambda c: f"{len(c['matched'])} of {c['answerable']}"),
            ("Key facts found", lambda c: f"{c['facts']:.0%}"),
            ("Correct refusals", lambda c: f"{c['correct_refusals']} of {c['must_refuse']}"),
            ("Wrong refusals", lambda c: f"{len(c['wrong_refusals'])} of {c['answerable']}"),
            ("Right chunk reached the Writer", lambda c: f"{c['reached']} of {c['gold']}"),
            ("Time per question (median)", lambda c: f"{c['seconds']:.0f} s"),
            ("Time for the whole run", lambda c: f"{c['minutes']:.0f} min"),
            ("Cost of the whole run", lambda c: f"${c['cost']:.2f}"),
            ("Failures: search", lambda c: str(len(c["failures"]["search"]))),
            ("Failures: Judge", lambda c: str(len(c["failures"]["judge"])) if c["has_judge"] else "-"),
            ("Failures: Writer", lambda c: str(len(c["failures"]["writer"]))),
            ("Failures: all", lambda c: str(sum(len(ids) for ids in c["failures"].values())))]
    head = f"| {split.capitalize()} | " + " | ".join(SYSTEMS.values()) + " |"
    return "\n".join([head, "|---|" + "---:|" * len(SYSTEMS)] + ["| " + name + " | " + " | ".join(cell(n[system, split]) for system in SYSTEMS) + " |" for name, cell in rows])


def unsupported_table(n):
    """The comparison the owner cares about most: complete answers with a claim their sources don't support, local against Haiku."""
    rows = (("One-shot, local", "oneshot-v2"), ("One-shot, Haiku", "oneshot-haiku"), ("Agent, local", "agent"), ("Agent, Haiku", "agent-haiku"))
    lines = ["| System | Dev: complete | With such a claim | Test: complete | With such a claim | Both: complete | With such a claim |", "|---|---:|---:|---:|---:|---:|---:|"]
    for label, system in rows:
        dev, test = n[system, "dev"], n[system, "test"]
        lines.append(f"| {label} | {len(dev['complete'])} | {len(dev['flagged_both'])} | {len(test['complete'])} | {len(test['flagged_both'])} | {len(dev['complete']) + len(test['complete'])} | **{len(dev['flagged_both']) + len(test['flagged_both'])}** |")
    return "\n".join(lines)


def haiku_claims_table(n):
    """Haiku's unsupported claims in complete answers, as reader A wrote them, or reader B if only B listed one."""
    lines = ["| System | Set | Question | What its sources don't support |", "|---|---|---|---|"]
    for system in HAIKU:
        for split in SPLITS:
            for item in sorted(n[system, split]["flagged_either"]):
                entry = READ[split][system][item]
                claims = entry["reader_a"]["unsupported"] or entry["reader_b"]["unsupported"]
                only_one = "" if item in n[system, split]["flagged_both"] else " (one reader only)"
                lines.append(f"| {SYSTEMS[system]} | {split} | `{item}` | {' '.join(claims)}{only_one} |")
    return "\n".join(lines)


def judge_table(n, mixed_run, runs):
    """The dev-only diagnostic: which Judge, side by side."""
    columns = (("Agent", n["agent", "dev"], "agent"), ("Agent-mixed", n[MIXED, "dev"], MIXED), ("Agent Haiku", n["agent-haiku", "dev"], "agent-haiku"), ("One-shot Haiku", n["oneshot-haiku", "dev"], "oneshot-haiku"))
    used = {name: (mixed_run if name == MIXED else runs[name, "dev"])["summary"]["overall"].get("rounds_used") for _, _, name in columns}
    rows = [("Judge", lambda c, name: {"agent": "local", MIXED: "local", "agent-haiku": "Haiku", "oneshot-haiku": "none"}[name]),
            ("Writer", lambda c, name: "local" if name == "agent" else "Haiku"),
            ("**Complete answers, read by hand**", lambda c, name: f"**{len(c['complete'])} of {c['answerable']}**"),
            ("Of those, with a claim their sources don't support", lambda c, name: str(len(c["flagged_both"]))),
            ("Wrong refusals", lambda c, name: f"{len(c['wrong_refusals'])} of {c['answerable']}"),
            ("Correct refusals", lambda c, name: f"{c['correct_refusals']} of {c['must_refuse']}"),
            ("Right chunk reached the Writer", lambda c, name: f"{c['reached']} of {c['gold']}"),
            ("Questions using 1 / 2 / 3 rounds", lambda c, name: " / ".join(str(used[name][r]) for r in "123") if used[name] else "-"),
            ("Time per question (median)", lambda c, name: f"{c['seconds']:.0f} s"),
            ("Time for the whole run", lambda c, name: f"{c['minutes']:.0f} min"),
            ("Cost of the whole run", lambda c, name: f"${c['cost']:.2f}")]
    return "\n".join(["| Dev | " + " | ".join(label for label, _, _ in columns) + " |", "|---|" + "---:|" * len(columns)] + ["| " + title + " | " + " | ".join(cell(c, name) for _, c, name in columns) + " |" for title, cell in rows])


def only_on_each(n, first, second, split):
    """The questions complete on one of the two systems and not on the other."""
    a, b = n[first, split]["complete"], n[second, split]["complete"]
    return a - b, b - a


def pairs_table(n):
    lines = ["| Compared | Set | Complete only on the first | Complete only on the second | Chance of a split this uneven if they were equally good |", "|---|---|---:|---:|---:|"]
    for split in ("test", "dev"):
        for first, second in PAIRS:
            only_first, only_second = only_on_each(n, first, second, split)
            lines.append(f"| {SYSTEMS[first]} against {SYSTEMS[second]} | {split} | {len(only_first)} | {len(only_second)} | {chance_of_split(len(only_first), len(only_second)):.2f} |")
    return "\n".join(lines)


def cost_table(n, runs, mixed_run):
    lines = ["| System | Set | Questions | Calls to Haiku | Tokens in | Tokens out | Of those, thinking | Cost of the run | Per question | Whole run |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for system in HAIKU:
        for split in SPLITS:
            c = n[system, split]
            entry = ledger["runs"][c["dir"]]
            calls = [r["tokens"] for r in runs[system, split]["items"].values() if r.get("tokens")] + [x["tokens"] for r in runs[system, split]["items"].values() for x in r.get("rounds", [])]
            thinking = sum(t.get("thinking_tokens") or 0 for t in calls) / sum(t["answer_tokens"] for t in calls)
            lines.append(f"| {SYSTEMS[system]} | {split} | {c['questions']} | {entry['calls']} | {entry['input_tokens']:,} | {entry['output_tokens']:,} | {thinking:.0%} | ${entry['spent']:.4f} | ${entry['spent'] / c['questions']:.4f} | {c['minutes']:.1f} min |")
    c = n[MIXED, "dev"]
    entry = ledger["runs"][c["dir"]]
    writer = [r["tokens"] for r in mixed_run["items"].values() if r.get("tokens")]
    thinking = sum(t.get("thinking_tokens") or 0 for t in writer) / sum(t["answer_tokens"] for t in writer)
    lines.append(f"| Agent-mixed (local Judge) | dev | {c['questions']} | {entry['calls']} | {entry['input_tokens']:,} | {entry['output_tokens']:,} | {thinking:.0%} | ${entry['spent']:.4f} | ${entry['spent'] / c['questions']:.4f} | {c['minutes']:.1f} min |")
    return "\n".join(lines)


def named(ids):
    return f"{len(ids)}: " + ", ".join(f"`{i}`" for i in sorted(ids)) if ids else "0"


def failures_table(n):
    lines = ["| System | Set | Search | Judge | Writer |", "|---|---|---|---|---|"]
    for split in SPLITS:
        for system in SYSTEMS:
            failures = n[system, split]["failures"]
            judge = named(failures["judge"]) if n[system, split]["has_judge"] else "-"
            lines.append(f"| {SYSTEMS[system]} | {split} | {named(failures['search'])} | {judge} | {named(failures['writer'])} |")
    return "\n".join(lines)


def wrong_table():
    lines = ["| System | Set | Question | Why it fails |", "|---|---|---|---|"]
    for split in SPLITS:
        for system in SYSTEMS:
            lines += [f"| {SYSTEMS[system]} | {split} | `{item}` | {reason} |" for item, reason in sorted(WRONG_THOUGH_COMPLETE[system, split].items())]
    return "\n".join(lines)


def row(n, key, split, size=False):
    return tuple(len(n[system, split][key]) if size else n[system, split][key] for system in SYSTEMS)


def steps(n, split, step):
    return tuple(len(n[system, split]["failures"][step]) for system in SYSTEMS)


def main():
    runs = {key: find_run(name) for key, name in RUNS.items()}
    missing = [RUNS[key] for key, run in runs.items() if run is None]
    if missing:
        raise SystemExit("These runs aren't there: " + ", ".join(missing))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    n = {key: numbers(key[0], run, key[1], ledger) for key, run in runs.items()}
    mixed_run = find_run(MIXED_RUN)
    if mixed_run is None:
        raise SystemExit(f"This run isn't there: {MIXED_RUN}")
    n[MIXED, "dev"] = numbers(MIXED, mixed_run, "dev", ledger)
    mixed_items, local_items, haiku_items = mixed_run["items"], runs["agent", "dev"]["items"], runs["agent-haiku", "dev"]["items"]
    mixed_times = {}
    for record in mixed_items.values():
        for step, seconds in record["times"].items():
            mixed_times[step] = mixed_times.get(step, 0) + seconds
    note = (ROOT / "prompts/closing_note.md").read_text(encoding="utf-8").strip()
    words = {s: statistics.median(len(runs[s, split]["items"][i]["answer"].replace(note, "").split()) for split in SPLITS for i in n[s, split]["complete"]) for s in SYSTEMS}
    test_runs = json.loads(TEST_RUNS.read_text(encoding="utf-8"))
    agent_test = runs["agent", "test"]["items"]
    all_read = [entry for split in SPLITS for system, items in READ[split].items() if system != MIXED for entry in items.values()]
    overtime = {system: runs[system, "dev"]["items"]["reference-01"] for system in SYSTEMS}
    combined = {system: (len(n[system, "dev"]["complete"]) + len(n[system, "test"]["complete"]), len(n[system, "dev"]["flagged_both"]) + len(n[system, "test"]["flagged_both"])) for system in SYSTEMS}
    below = {(s, a, b) for s in SPLITS for a, b in PAIRS if chance_of_split(*map(len, only_on_each(n, a, b, s))) < 0.05}

    claims = {"complete by hand": (row(n, "complete", "dev", True), row(n, "complete", "test", True)) == ((6, 9, 12, 15, 17), (5, 5, 4, 10, 10)),
              "complete by the matcher": (row(n, "matched", "dev", True), row(n, "matched", "test", True)) == ((9, 12, 16, 16, 18), (7, 6, 5, 11, 11)),
              "with unsupported claims, both readers": (row(n, "flagged_both", "dev", True), row(n, "flagged_both", "test", True)) == ((6, 6, 7, 5, 3), (5, 5, 2, 2, 3)),
              "the combined counts in the text": (combined["oneshot-v2"], combined["oneshot-haiku"], combined["agent"], combined["agent-haiku"]) == ((14, 11), (25, 7), (16, 9), (27, 6)),
              "key facts": ([round(f * 100) for f in row(n, "facts", "dev")], [round(f * 100) for f in row(n, "facts", "test")]) == ([51, 68, 78, 78, 85], [60, 69, 66, 85, 88]),
              "correct refusals": (row(n, "correct_refusals", "dev"), row(n, "correct_refusals", "test")) == ((4, 4, 5, 5, 5), (2, 1, 3, 4, 4)),
              "wrong refusals": (row(n, "wrong_refusals", "dev", True), row(n, "wrong_refusals", "test", True)) == ((2, 0, 1, 3, 0), (2, 1, 2, 1, 0)),
              "right chunk reached the Writer": (row(n, "reached", "dev"), row(n, "reached", "test")) == ((13, 22, 24, 22, 25), (12, 15, 14, 15, 16)),
              "median times": ([round(s) for s in row(n, "seconds", "dev")], [round(s) for s in row(n, "seconds", "test")]) == ([36, 63, 141, 12, 20], [54, 49, 118, 10, 21]),
              "the cost of a test run, as in the short version": (round(n["oneshot-haiku", "test"]["cost"], 2), round(n["agent-haiku", "test"]["cost"], 2)) == (0.04, 0.09),
              "a Haiku test run takes less time than the local one": n["oneshot-haiku", "test"]["minutes"] < n["oneshot-v2", "test"]["minutes"] and n["agent-haiku", "test"]["minutes"] < n["agent", "test"]["minutes"],
              "agent Haiku takes about twice one-shot Haiku's time and cost": all(1.6 < n["agent-haiku", s][k] / n["oneshot-haiku", s][k] < 2.4 for s in SPLITS for k in ("seconds", "cost")),
              "failures by step": (steps(n, "dev", "search"), steps(n, "dev", "writer"), steps(n, "test", "search"), steps(n, "test", "writer")) == ((13, 4, 2, 4, 1), (9, 15, 12, 8, 8), (5, 1, 0, 1, 0), (8, 13, 10, 5, 6))
              and (len(n["agent", "dev"]["failures"]["judge"]), len(n["agent", "test"]["failures"]["judge"]), len(n["agent-haiku", "dev"]["failures"]["judge"]), len(n["agent-haiku", "test"]["failures"]["judge"])) == (1, 3, 1, 0),
              "failures add up": all(sum(len(ids) for ids in c["failures"].values()) == c["questions"] - len(c["complete"]) - c["correct_refusals"] for c in n.values()),
              "the set sizes": all((c["questions"], c["answerable"], c["must_refuse"], c["gold"]) == ((32, 26, 6, 27) if key[1] == "dev" else (20, 16, 4, 17)) for key, c in n.items()),
              "every answer scored complete was read, and nothing else": all(set(READ[split][system]) == n[system, split]["matched"] for system in SYSTEMS for split in SPLITS) and set(READ["dev"][MIXED]) == n[MIXED, "dev"]["matched"],
              "the words each fail rests on": set(EVIDENCE) == {(s, split, i) for (s, split), wrong in WRONG_THOUGH_COMPLETE.items() for i in wrong}
              and all(all(w in runs[s, split]["items"][i]["answer"] for w in there) and not any(w in runs[s, split]["items"][i]["answer"] for w in gone) for (s, split, i), (there, gone) in EVIDENCE.items()),
              "the readers agreed on 109 of 111, and I ruled on the other 2": len(all_read) == 111 and sum(e["reader_a"]["verdict"] == e["reader_b"]["verdict"] for e in all_read) == 109 and sum(e["ruled"] for e in all_read) == 2
              and READ["dev"]["oneshot-v2"]["single-23"]["ruled"] and READ["test"]["oneshot-haiku"]["single-04"]["ruled"],
              "what the blind read changed on dev": READ["dev"]["baseline"]["sector-03"]["verdict"] == READ["dev"]["oneshot-v2"]["single-27"]["verdict"] == "pass" and "single-23" in WRONG_THOUGH_COMPLETE["agent", "dev"] and "single-23" in WRONG_THOUGH_COMPLETE["baseline", "dev"],
              "every test verdict of Phase 4A stood": {key: set(WRONG_THOUGH_COMPLETE[key]) for key in (("baseline", "test"), ("oneshot-v2", "test"), ("agent", "test"))} == {("baseline", "test"): {"single-08", "single-12"}, ("oneshot-v2", "test"): {"single-25"}, ("agent", "test"): {"single-08"}},
              "one-shot Haiku's wrong refusals all lack the right chunk": n["oneshot-haiku", "dev"]["wrong_refusals"] == {"single-09", "vocab-01", "lookup-01"} and n["oneshot-haiku", "test"]["wrong_refusals"] == {"lookup-04"}
              and not any(runs["oneshot-haiku", s]["items"][i]["retrieval"]["in_context"] for s in SPLITS for i in n["oneshot-haiku", s]["wrong_refusals"]),
              "reference-01: all five answer, and none names the law": all(not r["score"]["refused"] and "435/1976" not in r["answer"] and not r["retrieval"]["in_context"] for r in overtime.values()) and {r["retrieval"]["rank"] for r in overtime.values()} == {15, 27},
              "reference-01: Haiku's words": "Υ.Α. 11282/1979" in overtime["oneshot-haiku"]["answer"] and "Υ.Α. 11282/1979" in overtime["agent-haiku"]["answer"] and "υπερεργασίας" in overtime["agent-haiku"]["answer"]
              and not re.search("υπερωρ", overtime["agent-haiku"]["answer"]) and len(re.findall("υπερωρ", overtime["oneshot-haiku"]["answer"])) == 1 and "δεν αφορούν γενικά τα εργοστάσια" in overtime["oneshot-haiku"]["answer"],
              "single-14 and single-06 on one-shot Haiku say what the text says": "πληρώνονται ως υπερωρία" in runs["oneshot-haiku", "dev"]["items"]["single-14"]["answer"] and "single-14" in n["oneshot-haiku", "dev"]["complete"] and "το ήμισυ της αποζημίωσης" in runs["oneshot-haiku", "test"]["items"]["single-06"]["answer"] and "single-06" in n["oneshot-haiku", "test"]["complete"],
              "single-14 on agent Haiku": "η υπερεργασία καταβάλλεται" in runs["agent-haiku", "dev"]["items"]["single-14"]["answer"],
              "the local one-shot answers those three dev questions": not any(runs["oneshot-v2", "dev"]["items"][i]["score"]["refused"] for i in ("single-09", "vocab-01", "lookup-01")),
              "complete answers are about the same length": (round(words["oneshot-v2"]), round(words["agent"]), round(words["oneshot-haiku"]), round(words["agent-haiku"])) == (139, 124, 135, 151),
              "the baseline's shares": tuple(round(a / b * 100) for a, b in ((len(n["baseline", "dev"]["complete"]), 26), (len(n["baseline", "test"]["complete"]), 16), (n["baseline", "dev"]["reached"], 27), (n["baseline", "test"]["reached"], 17))) == (23, 31, 48, 71),
              "each test run used its own settings": all(all(runs[system, "test"]["summary"]["config"][key] == value for key, value in TEST_SETTINGS[system].items()) and runs[system, "test"]["summary"]["config"]["system"] == system for system in TEST_SETTINGS),
              "Haiku's dev and test runs used the same settings and model": all(all(runs[s, "dev"]["summary"]["config"][key] == runs[s, "test"]["summary"]["config"][key] for key in (*TEST_SETTINGS[s], "model")) for s in HAIKU),
              "the test runs are the claimed ones": all(test_runs[name]["run"] == runs[system, "test"]["dir"] for name, system in (("one-shot", "baseline"), ("oneshot-v2", "oneshot-v2"), ("agent", "agent"), ("oneshot-haiku", "oneshot-haiku"), ("agent-haiku", "agent-haiku"))),
              "the ledger covers every Haiku run and stays under the limits": all(n[s, split]["cost"] > 0 and n[s, split]["cost"] < 1 for s in HAIKU for split in SPLITS) and ledger["total"] < 3,
              "one reader alone adds one each on v2 dev and agent Haiku test": {key: len(c["flagged_either"]) - len(c["flagged_both"]) for key, c in n.items() if len(c["flagged_either"]) != len(c["flagged_both"])} == {("oneshot-v2", "dev"): 1, ("agent-haiku", "test"): 1},
              "agent-mixed's counts": (len(n[MIXED, "dev"]["matched"]), len(n[MIXED, "dev"]["complete"]), len(n[MIXED, "dev"]["flagged_both"]), len(n[MIXED, "dev"]["flagged_either"]), n[MIXED, "dev"]["wrong_refusals"], n[MIXED, "dev"]["correct_refusals"], n[MIXED, "dev"]["reached"]) == (17, 17, 3, 3, {"vocab-01", "lookup-01"}, 5, 24),
              "agent-mixed's time and cost": (round(n[MIXED, "dev"]["seconds"]), round(n[MIXED, "dev"]["minutes"]), round(n[MIXED, "dev"]["cost"], 2), round(n["agent-haiku", "dev"]["minutes"]), round(n["agent-haiku", "dev"]["cost"] - n[MIXED, "dev"]["cost"], 2)) == (76, 58, 0.05, 11, 0.08),
              "agent Haiku is about 4 times faster than agent-mixed": 3.5 < n[MIXED, "dev"]["seconds"] / n["agent-haiku", "dev"]["seconds"] < 4.5,
              "agent-mixed has no test run": not any(MIXED in claim for claim in test_runs) and not list((ROOT / "eval/results").glob("*agent-mixed*-test")),
              "agent-mixed's settings are agent-haiku's, with a local Judge": all(mixed_run["summary"]["config"][key] == runs["agent-haiku", "dev"]["summary"]["config"][key] for key in (*TEST_SETTINGS["agent-haiku"], "model")) and mixed_run["summary"]["config"]["judge"] == "local",
              "the local Judge made the same decisions in both runs": all([x["decision"] for x in local_items[i]["rounds"]] == [x["decision"] for x in mixed_items[i]["rounds"]] and [x["approved"] for x in local_items[i]["rounds"]] == [x["approved"] for x in mixed_items[i]["rounds"]] and [c["id"] for c in local_items[i]["chunks"]] == [c["id"] for c in mixed_items[i]["chunks"]] for i in local_items) and len(local_items) == 32,
              "local agent against agent-mixed, 7 to 2": tuple(map(len, only_on_each(n, MIXED, "agent", "dev"))) == (7, 2),
              "agent Haiku against agent-mixed, 3 to 3": tuple(map(len, only_on_each(n, "agent-haiku", MIXED, "dev"))) == (3, 3),
              "agent-mixed against one-shot Haiku": (len(n[MIXED, "dev"]["complete"]), len(n["oneshot-haiku", "dev"]["complete"]), n["oneshot-haiku", "dev"]["reached"], len(n["oneshot-haiku", "dev"]["wrong_refusals"])) == (17, 15, 22, 3),
              "extra rounds and the stop rule": (sum(len(r["rounds"]) > 1 for r in mixed_items.values()), sum(len(r["rounds"]) > 1 for r in haiku_items.values()), sum(any(x["stopped_by_code"] for x in r["rounds"]) for r in mixed_items.values()), sum(any(x["stopped_by_code"] for x in r["rounds"]) for r in haiku_items.values())) == (6, 4, 5, 0),
              "the right chunk first found in round 2": {i for i, r in mixed_items.items() if r["retrieval"] and r["retrieval"]["gold_first_round"] == 2} == {"single-09"} and {i for i, r in haiku_items.items() if r["retrieval"] and r["retrieval"]["gold_first_round"] == 2} == {"single-09", "lookup-01"},
              "lookup-01: the neighbour rule on Haiku's Judge, a refusal on the local one": mixed_items["lookup-01"]["refused_by_judge"] and len(mixed_items["lookup-01"]["rounds"]) == 3 and not mixed_items["lookup-01"]["retrieval"]["gold_judged"] and not any(x["approved"] for x in mixed_items["lookup-01"]["rounds"])
              and "lookup-01" in n["agent-haiku", "dev"]["complete"] and any(c["id"] == "glc-33848-010" and c["source"].startswith("next to") for x in haiku_items["lookup-01"]["rounds"] for c in x["chunks"]) and haiku_items["lookup-01"]["rounds"][0]["approved"] == ["glc-33848-011"],
              "vocab-01: no one has the right chunk, the mixed Writer refuses, agent Haiku has no key facts": not any(it["vocab-01"]["retrieval"]["in_context"] for it in (mixed_items, haiku_items)) and mixed_items["vocab-01"]["score"]["refused"] and not mixed_items["vocab-01"]["refused_by_judge"] and not haiku_items["vocab-01"]["score"]["refused"] and haiku_items["vocab-01"]["score"]["fact_share"] == 0,
              "on test the local Judge refused two that Haiku's didn't": n["agent", "test"]["wrong_refusals"] == {"single-25", "vocab-04"} and all(agent_test[i]["refused_by_judge"] for i in ("single-25", "vocab-04")) and {agent_test[i]["retrieval"]["rank"] for i in ("single-25", "vocab-04")} == {1, 2} and not n["agent-haiku", "test"]["wrong_refusals"],
              "the ledger stays the record of the measuring runs": "manual" not in ledger["runs"],
              "which comparisons fall below 0.05": below == EXPECTED_BELOW}
    broken = [claim for claim, holds in claims.items() if not holds]
    if broken:
        raise SystemExit("These claims in the report no longer hold, redo its text:\n- " + "\n- ".join(broken))

    tables = {split: main_table(n, split) for split in SPLITS}
    times = {}
    for record in runs["agent-haiku", "test"]["items"].values():
        for step, seconds in record["times"].items():
            times[step] = times.get(step, 0) + seconds
    both = {system: combined[system][1] / combined[system][0] for system in SYSTEMS}
    claims_in = {system: tuple(n[system, "dev"]["claims"][i] + n[system, "test"]["claims"][i] for i in (0, 1)) for system in SYSTEMS}
    lines = []

    def add(text=""):
        lines.append(text)

    add("# Final report: one-shot and agent, local and Haiku\n")
    add("Phases 4A and 4B. Five systems, the same questions, the same prompts. `scripts/final_report.py` writes this file from the stored runs and `eval/hand_read.json`, so don't edit it by hand.\n")
    add(SHORT_VERSION + "\n")
    add("## The five systems\n")
    add(SYSTEMS_TEXT + "\n")
    add("## The numbers\n")
    add("Dev has 32 questions: 26 can be answered and 6 must be refused, and 27 have a known right chunk. Test has 20: 16 and 4, and 17 with a known right chunk.\n")
    add(tables["dev"] + "\n")
    add(tables["test"] + "\n")
    add(TABLE_NOTES + "\n")
    add("## Unsupported claims: local against Haiku\n")
    add(unsupported_table(n) + "\n")
    add(UNSUPPORTED_TEXT.format(oneshot_local=both["oneshot-v2"], oneshot_haiku=both["oneshot-haiku"], agent_local=both["agent"], agent_haiku=both["agent-haiku"], claims=claims_in, complete={s: combined[s][0] for s in SYSTEMS}, words=words) + "\n")
    add(haiku_claims_table(n) + "\n")
    add("## What it shows\n")
    add(SHOWS.format(oneshot_seconds=n["oneshot-haiku", "test"]["seconds"], agent_seconds=n["agent-haiku", "test"]["seconds"]) + "\n")
    add("## Does the Judge need to be Haiku?\n")
    add("`agent-mixed` is the agent with a local Judge and a Haiku Writer, and nothing else changed. It ran on the dev questions only and doesn't touch test, so it's a diagnostic and not a result like the five above. Two more fresh readers read its complete answers blind, shuffled with 41 answers already read. They differed once, on the local agent's `single-23`, which I ruled a fail as before. Otherwise, on those 41, they matched every stored verdict and every flag of an unsupported claim. That shows how consistent one model is with itself, not that its readers are independent.\n")
    add(judge_table(n, mixed_run, runs) + "\n")
    add(JUDGE_TEXT.format(mixed_complete=len(n[MIXED, "dev"]["complete"]), mixed_flagged=len(n[MIXED, "dev"]["flagged_both"]), judge_share=mixed_times["judge"] / sum(mixed_times.values())) + "\n")
    add("## The overtime question\n")
    add(OVERTIME + "\n")
    add("## Cost and time per run\n")
    add(cost_table(n, runs, mixed_run) + "\n")
    add(f"Everything spent on measuring in Phase 4B, with the key check and three trial questions, comes to **${ledger['total']:.2f}** of the $3 limit. That counts the calls to Haiku, not the work of reading the answers. Haiku's thinking is most of its output and is billed as output, which is why a call costs about $0.002 and not the fraction of that the visible answer would suggest. In the agent's Haiku test run, the Judge takes {times['judge'] / sum(times.values()):.0%} of the time, the Writer {times['model answer'] / sum(times.values()):.0%} and the local Query Enhancer {times.get('enhancer', 0) / sum(times.values()):.0%}. The local systems cost no money here, but they tie up the machine: {n['agent', 'test']['minutes']:.0f} minutes for the agent's test run.\n")
    add("## How little this can show\n")
    add("**20 test questions is few.** 16 can be answered, so one answer is about 6 points. 4 must be refused, so one refusal is 25 points.\n")
    add("Taking the same questions one by one, and leaving out those where both are complete or neither is:\n")
    add(pairs_table(n) + "\n")
    add(PAIRS_TEXT + "\n")
    add(LIMITS.format(agreed=109) + "\n")
    add("## Failures by step\n")
    add("Test answers are listed by id only. Those scored incomplete weren't read.\n")
    add(failures_table(n) + "\n")
    add("## Answers scored complete that fail when read\n")
    add(wrong_table() + "\n")
    add("## How the runs were made\n")
    add(HOW_RUN.format(key_check=ledger["runs"]["key-check"]["spent"]) + "\n")
    add("## What comes next\n")
    add(NEXT)

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    readme = README.read_text(encoding="utf-8")
    for split, table in tables.items():
        if table not in readme:
            raise SystemExit(f"The {split} table in README.md differs from this one:\n\n" + table)


if __name__ == "__main__":
    main()
