"""Phase 4A: write docs/final-report.md from the stored runs. Needs no database and no model.

    .venv/bin/python -m labour_rag.evaluate --split test --system oneshot-v2
    .venv/bin/python -m labour_rag.evaluate --split test --system agent --name agent-3c1-qwen3-4b-semantic-units-limit4-test
    .venv/bin/python -I scripts/final_report.py

Each test run can be made once. The words around the numbers are hand-written (SHORT_VERSION, SHOWS, LIMITS, HOW_RUN, NEXT) and so are the verdicts
(WRONG_THOUGH_COMPLETE, NOTED), from reading every answer scored complete: the script stops if the claims it can check stop holding, and all of it must
be redone whenever the runs change. It also stops if the main table in README.md differs from the one here.
"""

import json
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

SPLITS = ("dev", "test")
SYSTEMS = {"baseline": "baseline", "oneshot-v2": "v2", "agent": "agent"}
PAIRS = (("agent", "oneshot-v2"), ("agent", "baseline"), ("oneshot-v2", "baseline"))
RUNS = {("baseline", "dev"): "oneshot-limit2-dev",
        ("baseline", "test"): "oneshot-limit2-test",
        ("oneshot-v2", "dev"): "oneshot-qwen3-4b-semantic-units-limit2-dev",
        ("oneshot-v2", "test"): "oneshot-qwen3-4b-semantic-units-limit2-test",
        ("agent", "dev"): "agent-3c1-qwen3-4b-semantic-units-limit4-dev",
        ("agent", "test"): "agent-3c1-qwen3-4b-semantic-units-limit4-test"}

# Scored as complete, but wrong when read. The rule, for all three systems: an answer fails if it states a key fact wrong or leaves one out, anywhere,
# short answer included. Errors outside the key facts are noted, not counted. The test verdicts were written before the labels were opened, and a second
# reader then read the same answers blind. The baseline's single-08 is the one verdict that changed after that: see LIMITS.
WRONG_THOUGH_COMPLETE = {
    ("baseline", "dev"): {
        "sector-02": "Its short answer allows overtime «πέραν των 120 ωρών ετησίως». The limit is at most 120 hours a year.",
        "sector-03": "It limits the rates to bakeries making over 3,000 okades of bread. The chunk says «παντός είδους αρτοποιεία».",
        "lookup-03": "It says the law makes 1 May a holiday. The law says it can be made one by a minister's decision, each year.",
    },
    ("oneshot-v2", "dev"): {
        "single-17": "Its short answer turns the exception around: dismissal depends on how long a health stoppage lasts. The key fact is a serious reason, given in writing.",
        "single-27": "It puts the Dormition on 21 August.",
        "lookup-01": "\"Subject to article 3\" isn't there: the matcher took a list number \"3.\" for it. The right chunk wasn't among its 8, so this counts as a search failure.",
    },
    ("agent", "dev"): {
        "single-10": "It starts the six months from the payment. The chunk says «αφ' ης κατέστη απαιτητή».",
        "sector-01": "It says 5 days for six years of service. The chunk says 30.",
        "sector-02": "It says «δεν απαιτεί προηγούμενη άδεια». The chunk says «μόνον κατόπιν αδείας».",
    },
    ("baseline", "test"): {
        "single-08": "The key fact names four years of service. The answer never says that, and says the law protects those with «περισσότερους από τέσσερις μήνες». I passed this at first: the second reader failed it, and that reading is right.",
        "single-12": "It says the 24 hours end at 24:00 «της επόμενης ημέρας». The chunk has them start at 00:01 and end at 24:00 the same day.",
    },
    ("oneshot-v2", "test"): {
        "single-25": "Its short answer opens with «Δεν χρειάζεται αποζημίωση» for a week away, unless the stoppage is over four days. A week is over four days, so the rule gives this person the opposite, and the explanation hedges instead of saying yes.",
    },
    ("agent", "test"): {
        "single-08": "It never says the illness must be proved. Its short answer skips those words with \"…\", and the matcher took «αποδεικνύει εγκατάλειψη», about something else, for that fact.",
    },
}

# What each verdict above rests on: words that must be in the answer, and words that must not.
EVIDENCE = {
    ("baseline", "dev", "sector-02"): (["πέραν των 120 ωρών"], []),
    ("baseline", "dev", "sector-03"): (["άνω των 3.000 οκάδων"], []),
    ("baseline", "dev", "lookup-03"): (["καθιερώνεται η 1η Μαΐου"], ["κάθε χρόνο", "κάθε έτος", "ετησίως"]),
    ("oneshot-v2", "dev", "single-17"): (["δεν υπερβαίνει το ανώτατο χρονικό διάστημα"], []),
    ("oneshot-v2", "dev", "single-27"): (["21 Αυγούστου"], []),
    ("oneshot-v2", "dev", "lookup-01"): ([], ["επιφύλαξη"]),
    ("agent", "dev", "single-10"): (["έγινε η καταβολή της αποζημίωσης"], []),
    ("agent", "dev", "sector-01"): (["πέντε τουλάχιστον ημέρας"], []),
    ("agent", "dev", "sector-02"): (["δεν απαιτεί προηγούμενη άδεια"], []),
    ("baseline", "test", "single-08"): (["περισσότερους από τέσσερις μήνες"], ["τέσσερα χρόνια", "τεσσάρων ετών", "τετραετ"]),
    ("baseline", "test", "single-12"): (["της επόμενης ημέρας"], []),
    ("oneshot-v2", "test", "single-25"): (["Δεν χρειάζεται αποζημίωση"], []),
    ("agent", "test", "single-08"): (["αποδεικνύει εγκατάλειψη"], ["αποδείξ", "αποδεδειγμέν"]),
}

# Test answers that pass, with something else wrong in them. Not counted. Every answer that passes is here, apart from the agent's lookup-02 and
# vocab-05, where neither reader found anything to note.
NOTED = {
    "baseline": {
        "lookup-04": "It ties the duty to safety and health and to directive 93/104. The chunk's last words are the heading of the next article.",
        "single-06": "The quote is invented: «πέντε έτη» isn't in the law, which says «τετραετή». The citation check catches this one.",
        "single-22": "**Close call.** The key facts are right, but it says a safety technician isn't obligatory for 20 to 49 people. Paragraph 2 of the same chunk says the employer must use one. It also turns a qualification rule for shipyards into a duty.",
        "single-31": "It says the law doesn't state whether the extra leave is on top of normal leave. Its own quote says «επί πλέον της νόμιμης».",
        "vocab-05": "It names the wrong law: Π.Δ. 119/1973, about bus staff, citing a chunk that doesn't hold the quote. The words are from Β.Δ. 748/1966 art. 14.",
    },
    "oneshot-v2": {
        "lookup-02": "It adds that workers can withdraw a dismissal and go to court for it. The chunk doesn't say that.",
        "single-06": "One line says \"more than four months\" of service where the law says four years; the next line has it right. It says the whole law was replaced, and only article 1 was.",
        "single-22": "**Close call.** The key facts are right, but the short answer says \"full-time employment\". The chunk's minimum is 75 hours a year, as its own next line says. It also invents a rule about doctors by risk category.",
        "single-31": "It says normal leave doesn't grow with the years. Α.Ν. 539/1945 art. 2 says it does, up to a limit.",
        "vocab-05": "It adds a three-day suspension as a penalty, from a rule about bus staff.",
    },
    "agent": {
        "lookup-04": "It says the duty is under the safety and health provisions. The chunk says under current legislation. The same heading trap as the baseline's.",
        "single-12": "It adds that collective agreements may shorten the rest. The cited chunk doesn't say that.",
    },
}

SHORT_VERSION = """**In short.** On the dev questions, which I used while building the agent, it is ahead: 13 of 26 answers complete, against 9 for one-shot v2 and 6 for the Phase 2 baseline. \
On the test questions, which no system was tuned on, that lead is gone: 4 of 16, against 5 and 5. That is a gap of one answer, so the test doesn't show that the agent is worse. It shows \
that the lead on dev can't be taken at face value. The agent does refuse better on both sets (3 of 4 on test, against 1 and 2), and it takes about 2.4 times as long as one-shot v2. On v2 and the \
agent, most failures are the Writer's."""

SYSTEMS_TEXT = """| System | How it answers | Search |
|---|---|---|
| Phase 2 baseline | Searches once and answers | bge-m3, semantic and keyword search mixed by equal-weight RRF, at most 2 chunks per act, the old repeat filter |
| One-shot v2 | Searches once and answers | qwen3-embedding:4b, semantic only, at most 2 chunks per act, repeats judged by numbers with a unit |
| Agent | Search, Judge, up to 3 rounds, Writer, citation check | The same search as v2 with at most 4 chunks per act, frozen at the tag `agent-frozen-3c1` |

All three use the same Writer: `ministral-3:8b`, with the same prompt and settings. So the differences come from what reaches the Writer, not from the Writer."""

TABLE_NOTES = """- **Complete answers, read by hand.** The matcher looks for every key fact, but it can't read meaning. So I read every answer it scored complete, and took away those that state a key fact wrong \
or leave one out, short answer included. I didn't read the other test answers, so the matcher's misses stay as failures on all three systems.
- **Right chunk reached the Writer.** The chunk that holds the answer was among those the Writer received.
- **Time** is the median for one question, from one run on one laptop. The baseline's runs are from the day before, and Phase 2 already noted that their times are weak.
- **Failures** add up to the questions minus complete answers and correct refusals. *Search:* the right chunk never reached the Writer (one-shots) or the Judge (agent). *Judge:* it held back the \
right chunk, or let through a question that should have been refused. *Writer:* it had the right chunk and still fell short. One-shots have no Judge, so answering a question that should have been \
refused counts as the Writer's."""

SHOWS = """- **The lead on dev didn't carry over.** Complete answers go 6, 9, 13 on dev, and 5, 5, 4 on test. Key facts go 51%, 68%, 78% on dev, and 60%, 69%, 66% on test. Dev isn't a fair place for the \
agent: I built its rules while reading those answers, and tuned the matcher on them. Test is the fairer number, but a small one (see the next section).
- **Refusing is where the agent leads on both sets.** 5 of 6 on dev against 4 and 4, and 3 of 4 on test against 2 and 1. It refuses wrongly about as often as the others, 2 of 16 on test against 2 and 1. Those two, `single-25` and \
`vocab-04`, were the Judge's, with the right chunk in places 1 and 2 of the search.
- **Better search alone doesn't give better answers.** On test, the right chunk reaches the Writer for 15 of 17 on v2, against 12 on the baseline, and key facts rise from 60% to 69%. Complete answers stay at 5.
- **The Writer is now the weak step.** On test it causes 13 of v2's 14 failures and 10 of the agent's 13, and search causes 1 and 0. Three of v2's 13 are questions it should have refused, with no Judge to catch them, so on the questions that can be \
answered both have 10. Some of those may be the matcher's misses, because test answers scored incomplete weren't read. `single-06`, `single-22` and `single-31` are complete on both one-shots and not on the agent, whose Writer had the right chunk for all three. \
I haven't read those three answers, as the rule for the test split says.
- **The agent costs time.** The median is 118 s against 49 s on test, and 141 s against 63 s on dev. The Judge takes {judge_share:.0%} of the agent's time on test.
- **Complete doesn't mean right in every sentence.** Of the 14 test answers that pass the hand read, 12 say something else their source doesn't support ([listed below](#other-mistakes-in-the-test-answers-that-pass)). \
They don't count under the rule, but anyone relying on these answers should check the source. The agent has such mistakes in 2 of its 4 answers, the one-shots in all 10. Both readers noted the same ones. I didn't plan to measure that, and the \
count is small, so it's a lead and not a result."""

LIMITS = """- **Test looks easier than dev.** The same baseline has 23% of answers complete on dev and 31% on test, and the right chunk reaches its Writer for 48% and 71%. Compare systems within a set, not across sets.
- **One run each.** A fixed seed makes a run repeatable, not typical. In Phase 3C.1, two small fixes changed 6 of 32 answers.
- **Two readers, no lawyer.** I (Claude) read the test answers blind: labels hidden, the answers to each question shuffled, verdicts saved before I opened the key. A fresh Claude agent then read the same 18 the same way, \
without my verdicts. We agreed on 17. On the baseline's `single-08` I had passed it and the second reader failed it, and its reasoning holds, so it fails here. That change came after the labels were open. Both readers are the same model, and \
the style of an answer can still give a system away, so this is not a fully independent check. The dev read had one reader and wasn't blind, so it may be a little generous too.
- **The order depends on close calls.** With the baseline's `single-08` still complete, test would read 6, 5 and 4. Both `single-22` answers and the baseline's `single-31` stay complete under the rule, each with a wrong statement right next to the key facts. If those failed, it would read 3, 4 and 4. So the order of the three on test means little.
- **I wrote the test set.** The owner reviewed 20 of its 52 items. Its expected answers follow our 1852-1999 data, not today's law.
- **Hand reading only takes away.** Answers scored incomplete weren't read on test. If the matcher missed a right answer, that answer stays a failure.
- **This test is now used.** I have read its complete answers. A later system can still make its own one run on it, but no change may come from what those answers say, and a clean second test needs new questions."""

HOW_RUN = """- **The guard.** `labour_rag/evaluate.py` now lets exactly two systems use the test split, once each, and only with their own settings: `oneshot-v2` and `agent`. The baseline keeps its Phase 2 run. Any other system or setting is refused.
- **The freeze.** `git diff agent-frozen-3c1 -- labour_rag prompts sql ':!labour_rag/evaluate.py'` printed nothing before the agent's run and after it. `evaluate` checks this itself, also when it continues an interrupted run, and refuses to start if anything changed.
- **The runs.** Both ran on 2026-11-05, detached from the session, one after the other, with no other model job. Each answered all 20 questions: v2 in about 17 minutes, the agent in about 52. An interrupted run would have continued where it stopped.
- **A correction.** Reading all three systems by one rule changed an earlier number. The Phase 3C report said 15 complete answers against 12 on dev. It's 13 against 9: my first read was too generous. [The agent report](agent-report.md) is corrected."""

NEXT = """Phase 4B replaces the Judge and the Writer with Claude Haiku, with a budget guard in code. The numbers above are a reason to try it, because the Writer is the weak step. They also limit what it can \
prove: dev isn't a fair set, and 16 test questions can't show a gap of a few answers."""


def failure_of(system, record, wrong):
    """Which step an answer fell short at, or None. An answer that fails when read goes through the same functions as one that lacks a key fact."""
    if record["id"] in wrong:
        record = {**record, "score": {**record["score"], "fact_share": 0}}
    step = agent_problem(record) if system == "agent" else problem(record)
    return "writer" if step == "reading" else step


def numbers(system, run, wrong):
    """What the table says about one system on one set."""
    items = run["items"]
    answerable = [r for r in items.values() if r["answerable"]]
    must_refuse = [r for r in items.values() if not r["answerable"]]
    gold = [r for r in items.values() if r["retrieval"]]
    matched = {r["id"] for r in answerable if r["score"]["fact_share"] == 1 and not r["score"]["refused"]}
    failures = {"search": [], "judge": [], "writer": []}
    for record in items.values():
        step = failure_of(system, record, wrong)
        if step:
            failures[step].append(record["id"])
    return {"answerable": len(answerable), "must_refuse": len(must_refuse), "gold": len(gold), "matched": matched, "complete": matched - set(wrong),
            "facts": run["summary"]["overall"]["fact_share"], "correct_refusals": sum(r["score"]["refused"] for r in must_refuse),
            "wrong_refusals": {r["id"] for r in answerable if r["score"]["refused"]}, "reached": sum(bool(r["retrieval"]["in_context"]) for r in gold),
            "seconds": run["summary"]["overall"]["seconds_median"], "failures": failures, "questions": len(items), "has_judge": system == "agent"}


def main_table(n):
    """The one table: every system on both sets, side by side. README.md carries the same one."""
    columns = [(system, split) for split in SPLITS for system in SYSTEMS]
    rows = [("**Complete answers, read by hand**", lambda c: f"**{len(c['complete'])} of {c['answerable']}**"),
            ("Complete answers, by the matcher alone", lambda c: f"{len(c['matched'])} of {c['answerable']}"),
            ("Key facts found", lambda c: f"{c['facts']:.0%}"),
            ("Correct refusals", lambda c: f"{c['correct_refusals']} of {c['must_refuse']}"),
            ("Wrong refusals", lambda c: f"{len(c['wrong_refusals'])} of {c['answerable']}"),
            ("Right chunk reached the Writer", lambda c: f"{c['reached']} of {c['gold']}"),
            ("Time per question (median)", lambda c: f"{c['seconds']:.0f} s"),
            ("Failures: search", lambda c: str(len(c["failures"]["search"]))),
            ("Failures: Judge", lambda c: str(len(c["failures"]["judge"])) if c["has_judge"] else "-"),
            ("Failures: Writer", lambda c: str(len(c["failures"]["writer"]))),
            ("Failures: all", lambda c: str(sum(len(ids) for ids in c["failures"].values())))]
    head = "| Measure | " + " | ".join(f"{split.capitalize()}: {SYSTEMS[system]}" for system, split in columns) + " |"
    return "\n".join([head, "|---|" + "---:|" * len(columns)] + ["| " + name + " | " + " | ".join(cell(n[column]) for column in columns) + " |" for name, cell in rows])


def only_on_each(n, first, second, split):
    """The questions complete on one of the two systems and not on the other."""
    a, b = n[first, split]["complete"], n[second, split]["complete"]
    return a - b, b - a


def pairs_table(n):
    lines = ["| Compared | Set | Complete only on the first | Complete only on the second | Chance of a split this uneven if they were equally good |", "|---|---|---|---|---:|"]
    for split in SPLITS:
        for first, second in PAIRS:
            only_first, only_second = only_on_each(n, first, second, split)
            lines.append(f"| {SYSTEMS[first]} against {SYSTEMS[second]} | {split} | {len(only_first)} | {len(only_second)} | {chance_of_split(len(only_first), len(only_second)):.2f} |")
    return "\n".join(lines)


def named(ids):
    return f"{len(ids)}: " + ", ".join(f"`{i}`" for i in sorted(ids)) if ids else "0"


def failures_table(n):
    lines = ["| System | Set | Search | Judge | Writer |", "|---|---|---|---|---|"]
    for split in SPLITS:
        for system in SYSTEMS:
            failures = n[system, split]["failures"]
            judge = named(failures["judge"]) if system == "agent" else "-"
            lines.append(f"| {SYSTEMS[system]} | {split} | {named(failures['search'])} | {judge} | {named(failures['writer'])} |")
    return "\n".join(lines)


def wrong_table():
    lines = ["| System | Set | Question | Why it fails |", "|---|---|---|---|"]
    for (system, split), wrong in WRONG_THOUGH_COMPLETE.items():
        lines += [f"| {SYSTEMS[system]} | {split} | `{item}` | {reason} |" for item, reason in wrong.items()]
    return "\n".join(lines)


def noted_table():
    lines = ["| System | Question | What else is wrong |", "|---|---|---|"]
    for system, notes in NOTED.items():
        lines += [f"| {SYSTEMS[system]} | `{item}` | {note} |" for item, note in notes.items()]
    return "\n".join(lines)


def counts(n, key, split):
    return tuple(n[system, split][key] for system in SYSTEMS)


def sizes(n, key, split):
    return tuple(len(n[system, split][key]) for system in SYSTEMS)


def steps(n, split, step):
    return tuple(len(n[system, split]["failures"][step]) for system in SYSTEMS)


def main():
    runs = {key: find_run(name) for key, name in RUNS.items()}
    missing = [RUNS[key] for key, run in runs.items() if run is None]
    if missing:
        raise SystemExit("These runs aren't there: " + ", ".join(missing))
    n = {key: numbers(key[0], run, WRONG_THOUGH_COMPLETE[key]) for key, run in runs.items()}
    agent_test = runs["agent", "test"]["items"]
    times = {}
    for record in agent_test.values():
        for step, seconds in record["times"].items():
            times[step] = times.get(step, 0) + seconds
    minutes = {system: sum(s for r in runs[system, "test"]["items"].values() for s in r["times"].values()) / 60 for system in ("oneshot-v2", "agent")}
    test_runs = json.loads(TEST_RUNS.read_text(encoding="utf-8"))
    side_errors = {system: len(notes) for system, notes in NOTED.items()}

    claims = {"complete by hand": (sizes(n, "complete", "dev"), sizes(n, "complete", "test")) == ((6, 9, 13), (5, 5, 4)),
              "complete by the matcher": (sizes(n, "matched", "dev"), sizes(n, "matched", "test")) == ((9, 12, 16), (7, 6, 5)),
              "key facts": ([round(f * 100) for f in counts(n, "facts", "dev")], [round(f * 100) for f in counts(n, "facts", "test")]) == ([51, 68, 78], [60, 69, 66]),
              "correct refusals": (counts(n, "correct_refusals", "dev"), counts(n, "correct_refusals", "test")) == ((4, 4, 5), (2, 1, 3)),
              "wrong refusals": (sizes(n, "wrong_refusals", "dev"), sizes(n, "wrong_refusals", "test")) == ((2, 0, 1), (2, 1, 2)),
              "right chunk reached the Writer": (counts(n, "reached", "dev"), counts(n, "reached", "test")) == ((13, 22, 24), (12, 15, 14)),
              "median times": ([round(s) for s in counts(n, "seconds", "dev")], [round(s) for s in counts(n, "seconds", "test")]) == ([36, 63, 141], [54, 49, 118]),
              "the agent takes about 2.4 times as long as v2 on test": round(n["agent", "test"]["seconds"] / n["oneshot-v2", "test"]["seconds"], 1) == 2.4,
              "failures by step": (steps(n, "dev", "search"), steps(n, "dev", "writer"), steps(n, "test", "search"), steps(n, "test", "writer")) == ((13, 4, 2), (9, 15, 11), (5, 1, 0), (8, 13, 10))
              and (len(n["agent", "dev"]["failures"]["judge"]), len(n["agent", "test"]["failures"]["judge"])) == (1, 3),
              "failures add up": all(sum(len(ids) for ids in c["failures"].values()) == c["questions"] - len(c["complete"]) - c["correct_refusals"] for c in n.values()),
              "the set sizes": all((c["questions"], c["answerable"], c["must_refuse"], c["gold"]) == ((32, 26, 6, 27) if key[1] == "dev" else (20, 16, 4, 17)) for key, c in n.items()),
              "a wrong answer was scored complete by the matcher": all(set(wrong) <= n[key]["matched"] for key, wrong in WRONG_THOUGH_COMPLETE.items()),
              "the words each wrong verdict rests on": set(EVIDENCE) == {(s, split, i) for (s, split), wrong in WRONG_THOUGH_COMPLETE.items() for i in wrong}
              and all(all(w in runs[s, split]["items"][i]["answer"] for w in there) and not any(w in runs[s, split]["items"][i]["answer"] for w in gone) for (s, split, i), (there, gone) in EVIDENCE.items()),
              "the Judge refused the two with the right chunk first and second": n["agent", "test"]["wrong_refusals"] == {"single-25", "vocab-04"}
              and all(agent_test[i]["refused_by_judge"] for i in ("single-25", "vocab-04")) and {agent_test[i]["retrieval"]["rank"] for i in ("single-25", "vocab-04")} == {1, 2},
              "the three lost by the agent's Writer": all(i in n["baseline", "test"]["complete"] and i in n["oneshot-v2", "test"]["complete"] and i not in n["agent", "test"]["complete"] and agent_test[i]["retrieval"]["in_context"] and i in n["agent", "test"]["failures"]["writer"] for i in ("single-06", "single-22", "single-31")),
              "14 pass, 12 with something else wrong": sum(len(c["complete"]) for key, c in n.items() if key[1] == "test") == 14 and sum(side_errors.values()) == 12 and side_errors == {"baseline": 5, "oneshot-v2": 5, "agent": 2},
              "the notes are about answers that pass": all(set(notes) <= n[system, "test"]["complete"] for system, notes in NOTED.items()),
              "the close calls move test to 6, 5, 4 or to 3, 4, 4": {"single-22", "single-31"} <= n["baseline", "test"]["complete"] and "single-22" in n["oneshot-v2", "test"]["complete"] and "single-22" not in n["agent", "test"]["complete"] and "single-31" not in n["agent", "test"]["complete"] and "single-08" in n["baseline", "test"]["matched"],
              "the baseline's shares": tuple(round(a / b * 100) for a, b in ((len(n["baseline", "dev"]["complete"]), 26), (len(n["baseline", "test"]["complete"]), 16), (n["baseline", "dev"]["reached"], 27), (n["baseline", "test"]["reached"], 17))) == (23, 31, 48, 71),
              "each test run used its own settings": all(all(runs[system, "test"]["summary"]["config"][key] == value for key, value in TEST_SETTINGS[system].items()) and runs[system, "test"]["summary"]["config"]["system"] == system for system in TEST_SETTINGS),
              "the test runs are the claimed ones": test_runs["one-shot"]["run"] == runs["baseline", "test"]["dir"] and test_runs["oneshot-v2"]["run"] == runs["oneshot-v2", "test"]["dir"] and test_runs["agent"]["run"] == runs["agent", "test"]["dir"],
              "the run lengths": (round(minutes["oneshot-v2"]), round(minutes["agent"])) == (17, 52),
              "the Writer's failures on questions that can be answered": {system: sum(runs[system, "test"]["items"][i]["answerable"] for i in n[system, "test"]["failures"]["writer"]) for system in ("oneshot-v2", "agent")} == {"oneshot-v2": 10, "agent": 10},
              "only agent against baseline on dev stands out": {(s, a, b): chance_of_split(*map(len, only_on_each(n, a, b, s))) < 0.05 for s in SPLITS for a, b in PAIRS} == {(s, a, b): (s, a, b) == ("dev", "agent", "baseline") for s in SPLITS for a, b in PAIRS}}
    broken = [claim for claim, holds in claims.items() if not holds]
    if broken:
        raise SystemExit("These claims in the report no longer hold, redo its text:\n- " + "\n- ".join(broken))

    table = main_table(n)
    lines = []

    def add(text=""):
        lines.append(text)

    add("# Final report: one-shot against the agent\n")
    add("Phase 4A. Three systems, the same questions, the same local Writer. `scripts/final_report.py` writes this file from the stored runs, so don't edit it by hand.\n")
    add(SHORT_VERSION + "\n")
    add("## The three systems\n")
    add(SYSTEMS_TEXT + "\n")
    add("## The numbers\n")
    add("Dev has 32 questions: 26 can be answered and 6 must be refused, and 27 have a known right chunk. Test has 20: 16 and 4, and 17 with a known right chunk.\n")
    add(table + "\n")
    add(TABLE_NOTES + "\n")
    add("## What it shows\n")
    add(SHOWS.format(judge_share=times["judge"] / sum(times.values())) + "\n")
    add("## How little this can show\n")
    add("**20 questions is few.** 16 can be answered, so one answer is about 6 points. 4 must be refused, so one refusal is 25 points. No two systems differ by more than 1 complete answer on test.\n")
    add("Taking the same questions one by one, and leaving out those where both are complete or neither is:\n")
    add(pairs_table(n) + "\n")
    add("Only the agent against the baseline on dev stands out, and that is the set the agent was built on.\n")
    add(LIMITS + "\n")
    add("## Failures by step\n")
    add("Test answers are listed by id only. Those scored incomplete weren't read.\n")
    add(failures_table(n) + "\n")
    add("## Answers scored complete that fail when read\n")
    add(wrong_table() + "\n")
    add("## Other mistakes in the test answers that pass\n")
    add("These are outside the key facts, so they don't count against an answer. The agent's `lookup-02` and `vocab-05` had nothing to note.\n")
    add(noted_table() + "\n")
    add("## How the runs were made\n")
    add(HOW_RUN + "\n")
    add("## What comes next\n")
    add(NEXT)

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")
    if table not in README.read_text(encoding="utf-8"):
        raise SystemExit("The main table in README.md differs from this one:\n\n" + table)


if __name__ == "__main__":
    main()
