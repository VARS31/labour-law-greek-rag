"""Phases 3C and 3C.1: write docs/agent-report.md from the stored runs. Needs no database and no model.

    .venv/bin/python -m labour_rag.evaluate --split dev                  # the one-shot, about half an hour
    .venv/bin/python -m labour_rag.evaluate --split dev --system agent --name agent-3c1-qwen3-4b-semantic-units-limit4-dev
    .venv/bin/python -I scripts/agent_report.py

The agent's run takes about an hour and a half. The run of Phase 3C was made with the code of commit d38df94, and it can't be repeated with today's.

The words around the numbers are hand-written (FIXES, CHANGED, FIXES_NOTES, RESULT, ROUNDS, FAILURES, NEXT, LIMITS) and come from reading the
answers: the script stops if the claims it can check stop holding, and all of them must be redone whenever the runs change.
"""

import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag.agent import trace_lines  # noqa: E402
from labour_rag.ask import closing_note  # noqa: E402
from labour_rag.evaluate import agent_problem  # noqa: E402
from scripts.eval_report import CATEGORY_TEXT, find_run  # noqa: E402
from scripts.final_report import WRONG_THOUGH_COMPLETE as READ_BY_HAND  # noqa: E402

REPORT = ROOT / "docs/agent-report.md"
ONE_SHOT = "oneshot-qwen3-4b-semantic-units-limit2-dev"
AGENT = "agent-qwen3-4b-semantic-units-limit4-dev"
AGENT_FIXED = "agent-3c1-qwen3-4b-semantic-units-limit4-dev"
# Scored as complete, but wrong when read. The verdicts and their reasons are in scripts/final_report.py, which reads all three systems the same way. No answer changed between 3C and 3C.1 on these.
WRONG_THOUGH_COMPLETE = {"agent": set(READ_BY_HAND["agent", "dev"]), "agent-3c1": set(READ_BY_HAND["agent", "dev"]),
                         "one-shot": set(READ_BY_HAND["oneshot-v2", "dev"])}

FIXES = """After Phase 3C, two fixes went in. **(a)** Searching stops once the Judge has approved a chunk that answers directly and applies to this person. **(b)** Round 2 also reads \
the next 8 places on the plain question's list. The dev questions ran once more with both, and this is the agent that goes to Phase 4, frozen. \
[How a question is answered](how-a-question-is-answered.md) describes it step by step and traces `single-09`.

**A small gain, and the first real rescue.** Round 2 found the right chunk for `single-09`, at rank 15, and the writer gave the main rule where 3C refused after almost 6 minutes. Wrong \
refusals fall from {o_wr} to {f_wr}, key facts rise from {o_facts:.0%} to {f_facts:.0%}, and no question lost a key fact. But no new answer is complete, by matching or by hand. And it's one \
question of 27: it shows the fix can work, not how often it will."""

# id, rounds, what happened, how it ended: from reading the answers
CHANGED = [("`single-09`", "3 → 2", "Round 2 read rank 15, the right chunk. The Judge called it relevant but still asked to search on, and the code stopped it.",
            "**Better, not clean.** The main rule is right and cited. But it doesn't name Ν. 2112/1920, two quotes fail the check, and it says a change without a written document is void, citing "
            "chunks that don't say so: Π.Δ. 156/1994 only requires the document."),
           ("`single-27`", "2 → 1", "The right chunk was approved in round 1, and the code stopped there.", "Same. The four holidays are right and it's still complete. The writer reads 3 chunks instead of 6."),
           ("`vocab-03`", "2 → 1", "Stopped in round 1, so the Judge couldn't reject the right chunk in round 2. The writer has it, but third, because the Judge marked it only partly.",
            "Same wrong answer. It answers from the weekend ban in [1], not the night ban in [3]. The failure moved from the Judge to the writer."),
           ("`vocab-01`", "2 → 1", "Stopped in round 1, on a decree about ordinary workplaces that the Judge called relevant.", "Same wrong law, Π.Δ. 16/1996. The right chunk is at rank 19, which round 2 can't reach anyway."),
           ("`reference-01`", "2 → 2", "Round 2 also read ranks 9 to 16. The general rate is in a law we don't have.", "Same wrong 25%. The citation check now passes only because the writer copied its quote without a stray word."),
           ("`refuse-06`", "3 → 2", "Round 2 found a 1912 article on penalties for parents who send a child to work. The Judge called it relevant to custody, and the code stopped.",
            "Still a right refusal, but the writer wrote it, with one sentence on the 1912 law. The misleading pointer to Ν.Δ. 3868/1958 is gone.")]

FIXES_NOTES = """**The stop rule believes the Judge.** It fired {stops} times. On `single-09` and `single-27` the chunk really answers. On the other 3 the Judge called the wrong chunk relevant, as the table shows. It cost \
no key fact here. But on `refuse-06` only the writer's own refusal stood between a question outside labour law and an answer, where 3C's Judge refused in round 3. Phase 4 may show this going worse.

**Further reading reaches only so far.** Of the 4 questions whose right chunk never reached the Judge in 3C, it could reach one. Its 8 places end at rank 16 or 17 on these questions, and the others rank 19 (`vocab-01`), 27 (`reference-01`) and 30 (`lookup-01`).

**It isn't measurably faster.** The Judge runs {r_f} rounds instead of {r_o} and uses {token_drop:.0%} fewer tokens, but the run took {t_f:.0f} minutes against {t_o:.0f}. Stopping saves rounds, and further reading makes \
round 2 bigger: 4 chunks more on each of the 6 questions that still reach it. The clock can't settle it either. The {n_same} questions that did exactly the same work took {same_o:.0f} and {same_f:.0f} minutes in all, so the machine's speed \
was the same overall, but one by one they took from {low:.1f} to {high:.1f} times as long in the second run, depending on when they ran. So don't compare one question's time between the two runs, and that includes the medians above."""

RESULT = """**The agent gives better answers, and the Judge's filter does that, not the extra rounds.** Checked by hand, the agent gave a \
complete answer to {a_hand} of {n} answerable dev questions, against {o_hand} for the one-shot. Key facts rise from {o_facts:.0%} to {a_facts:.0%}. \
It refused {a_cr} of the {u} questions it should refuse, against {o_cr}, but it also wrongly refused {a_wr} it could have answered, against {o_wr}. It is \
much slower: a median of {a_time:.0f} s per question against {o_time:.0f} s.

**Round 2 rescued no answer on these questions.** The right chunk reached the Judge in round 1 for {judged} of {gold} questions, and never for the other \
{never}. {multi} questions used more than one round: 1 got better, 2 got worse and 6 changed nothing. Those extra rounds took {extra:.0f} of the {total:.0f} \
minutes. So the example of a rescue that the brief asks for doesn't exist here, and the report says so below.

**The gain comes from showing the writer less.** The Judge keeps about a third of what round 1 finds ({approved} of {shown} chunks), so the writer reads \
{a_chunks:.1f} chunks on average instead of {o_chunks:.1f}. It rejects rules for other groups, and it prefers the newest act: on `single-15` it dropped the 14 and 15 week \
rules and kept the 16 week one, which Phase 3B had left for someone to decide.

**Don't read too much into the size of this.** The agent found more key facts on {better} questions and fewer on {worse}, a split that chance alone would give \
about {chance:.0%} of the time. This run also can't fully separate the Judge's filter from limit 4, or from how much the writer reacts to small changes in what it reads. I \
changed the Judge's prompt once, after trying it on 5 of these questions, and the test questions weren't touched."""

# id, label, how it ended, and why: from reading the traces and the answers
ROUNDS = [("`refuse-06`", 3, "Better", "Rounds 1 and 2 kept a chunk on family allowances as partly useful. Round 3 rejected it and refused, which is right. The one-shot answered from another decree on family allowances."),
          ("`vocab-03`", 2, "Worse", "Round 1 approved the right chunk. Round 2 rejected it and lost the answer. See the trace below."),
          ("`reference-01`", 2, "Worse", "Round 1 said the general rule was missing, which is right. Round 2 found nothing new, yet the Judge called the same 1979 chunk relevant and answered 25%."),
          ("`single-27`", 2, "Same", "The right chunk was approved in round 1. The Judge wanted one list of all holidays, and 140 s later it answered from the same chunk."),
          ("`sector-03`", 2, "Same", "The right chunk was marked \"partly\" in round 1 and \"relevant\" in round 2, with nothing new to compare it with."),
          ("`vocab-01`", 2, "Same", "The right document never came up. Round 2 only added more chunks from the wrong decree."),
          ("`single-09`", 3, "Same", "The right chunk never reached the Judge. It refused after almost 6 minutes, and the refusal names the right law."),
          ("`refuse-04`", 3, "Same", "The question names a law from 2010, so it could have refused in round 1. It took three rounds to say so."),
          ("`lookup-01`", 3, "Same", "The right chunk never came up, and the Judge rightly rejected what did. See the data problem in `lookup-01` below the table.")]

FAILURES = [("sector-01", "Writer", "The right chunk, and the score didn't see the mistake",
             "The Judge did everything right: it rejected the rule for private employees and approved the one right chunk. The writer then told a worker with six years' "
             "service that the notice is 5 days, and that their contract lasted \"between one and two years\". The right answer is 30 days. It counts as complete because \"30\" "
             "appears further down, in the list of cases. This is why the numbers above were checked by hand. No search or Judge can fix this one."),
            ("vocab-03", "Judge", "It rejected the right chunk it had approved one round earlier",
             "The chunk says «Απαγορεύεται πάσα εργασία προς παρασκευήν, ζύμωσιν και έψησιν άρτου», and the Judge's reason in round 2 is that it speaks of night work in general, "
             "\"not of kneading\". The writer then answered from an article about the weekend ban. The one-shot, with no Judge, got the hours right."),
            ("reference-01", "Judge", "It rejected five rules for other groups, then fell for the sixth",
             "In round 1 it rejected the rules for textile mills, furniture makers, KTEL, kitchens and cinemas, which the one-shot can't do. But it kept a 1979 decision that pays 25% for "
             "hours beyond the agreed week, and the general rate is in Ν. 435/1976, which isn't in our data. The chunks pointing to that law rank too low to reach the Judge. So the answer "
             "is the same wrong 25% as the one-shot's."),
            ("vocab-01", "Search", "The word never comes up, so the Judge chooses among wrong chunks",
             "The right document says \"εργοτάξια\" and the question says \"οικοδομές\". Plain search misses it, and the Query Enhancer never produces that word. The Judge can only "
             "choose from what it gets, and it approved 7 chunks, mostly from a decree about ordinary workplaces. Nothing warned the reader."),
            ("single-09", "Search", "Almost six minutes, then an honest refusal that counts as wrong",
             "The right chunk ranks 15th for the plain question, and only the first 8 are read. Round 2 searches only the phrasings, so nobody ever reads further down that list. After three "
             "rounds the Judge refused, and the refusal points to Ν. 2112/1920, the right law. The one-shot wrote a wrong answer instead. The score calls the refusal wrong, but I'd rather have it.")]

NEXT = """Phase 3C listed four things to try. Phase 3C.1 did the first two, and the agent is now frozen, so the other two would be a new system with its own run, after Phase 4.

1. **Done: stop when a right chunk is in hand.** It saves a round when the Judge is right, on `single-27`. It keeps the right chunk in front of the writer on `vocab-03`, but the answer is no better.
2. **Done: let round 2 read further down the plain question's list.** It got the one rescue, `single-09`. `vocab-01` stops before reaching it, and its right chunk is too far down in any case.
3. **A stronger writer.** {writer} of the {problems} failures in 3C.1 are the writer's, with the right chunk in front of it. Phase 4 can test that.
4. **A faster, more careful Judge.** It takes {judge_share:.0%} of the agent's time, mostly writing one verdict for each chunk. Now that its "relevant" can end the search, its mistakes also cost more."""

LIMITS = """- **27 questions, read closely.** One question is about 4 points. I read these answers, and I changed the Judge's prompt once after trying 5 of them, so the numbers flatter the agent. The test questions weren't touched, and the agent's one test run belongs to Phase 4.
- **One run of a model that reacts to small changes.** The Judge runs at temperature 0, but a small change in the chunks can change its verdicts, as `vocab-03` shows.
- **The time depends on the machine.** The one-shot's median here is 63 s, and it was 36 s in Phase 2 on a quieter machine. The Mac also slept during part of the agent run, which the per-question times leave out. Compare the two systems roughly, not to the second.
- **A refusal's pointer can mislead.** On `refuse-06` the refusal says the chunks point to Ν.Δ. 3868/1958, a law on family allowances named in an earlier round, although the question is about custody. All 11 claims that a law isn't in our data were checked and are true, but true doesn't always mean relevant.
- **The scores can't read meaning.** Besides the wrong answers named above, `single-01` is right on the main point and scores only 1 of 3 facts. I read the answers scored as complete, not all the others."""


def share(group, key, total):
    return round(group[key] * total)


def chance_of_split(wins, losses):
    total = wins + losses
    return min(1.0, 2 * sum(math.comb(total, i) for i in range(max(wins, losses), total + 1)) / 2 ** total)


def complete(run, name):
    return {i for i, r in run["items"].items() if r["answerable"] and r["score"]["fact_share"] == 1} - WRONG_THOUGH_COMPLETE[name]


def overall_table(one, agent, one_group, agent_group):
    a, u, gold = agent_group["answerable"], agent_group["unanswerable"], agent_group["with_gold_chunks"]
    rows = [("Key facts found", f"{one_group['fact_share']:.0%}", f"{agent_group['fact_share']:.0%}"),
            ("Answers with every key fact, by matching", f"{share(one_group, 'all_facts', a)} of {a}", f"{share(agent_group, 'all_facts', a)} of {a}"),
            ("Answers with every key fact, checked by hand", f"**{len(complete(one, 'one-shot'))} of {a}**", f"**{len(complete(agent, 'agent'))} of {a}**"),
            ("Correct refusals", f"{one_group['correct_refusals']} of {u}", f"{agent_group['correct_refusals']} of {u}"),
            ("Wrong refusals", f"{one_group['wrong_refusals']} of {a}", f"{agent_group['wrong_refusals']} of {a}"),
            ("The writer saw the right chunk (recall)", f"{share(one_group, 'recall_at_8', gold)} of {gold}", f"{share(agent_group, 'recall_at_8', gold)} of {gold}"),
            ("Citation check passed", f"{share(one_group, 'check_passed', a)} of {a}", f"{share(agent_group, 'check_passed', a)} of {a}"),
            ("Rounds used", "1", f"{agent_group['rounds_used']['1']} questions took 1, {agent_group['rounds_used']['2']} took 2, {agent_group['rounds_used']['3']} took 3"),
            ("Median time per question", f"{one_group['seconds_median']:.0f} s", f"{agent_group['seconds_median']:.0f} s")]
    return "\n".join(["| Measure | One-shot | Agent |", "|---|---:|---:|"] + [f"| {m} | {o} | {g} |" for m, o, g in rows])


def category_table(one, agent):
    """Per category, each cell one-shot → agent."""
    lines = ["| Category | Questions | Key facts | Every fact | Correct refusals | Wrong refusals | Saw the right chunk | Rounds (1/2/3) | Median time |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, (label, _, _) in CATEGORY_TEXT.items():
        o, g = one["summary"]["by_category"][name], agent["summary"]["by_category"][name]
        a, u, gold = g["answerable"], g["unanswerable"], g["with_gold_chunks"]
        facts = f"{o['fact_share']:.0%} → {g['fact_share']:.0%}" if a else "-"
        every = f"{share(o, 'all_facts', a)} → {share(g, 'all_facts', a)} of {a}" if a else "-"
        seen = f"{share(o, 'recall_at_8', gold)} → {share(g, 'recall_at_8', gold)} of {gold}" if gold else "-"
        refusals = f"{o['correct_refusals']} → {g['correct_refusals']} of {u}" if u else "-"
        wrong = f"{o['wrong_refusals']} → {g['wrong_refusals']} of {a}" if a else "-"
        used = g["rounds_used"]
        lines.append(f"| {label} | {g['questions']} | {facts} | {every} | {refusals} | {wrong} | {seen} | {used['1']}/{used['2']}/{used['3']} | {o['seconds_median']:.0f} s → {g['seconds_median']:.0f} s |")
    return "\n".join(lines)


def problems_of(group):
    """Failures by who caused them. The code can't see the answers that score as complete and are wrong when read."""
    kinds = {kind: group["agent_problems"][kind] for kind in ("search", "judge", "writer")}
    kinds["writer"] += len(WRONG_THOUGH_COMPLETE["agent"])
    return kinds


def judge_work(run):
    """Rounds, chunks read and tokens: the Judge's work, in numbers that don't depend on the machine."""
    rounds = [r for item in run["items"].values() for r in item["rounds"]]
    return len(rounds), sum(len(r["chunks"]) for r in rounds), sum(r["tokens"]["prompt_tokens"] + r["tokens"]["answer_tokens"] for r in rounds)


def minutes(items):
    return sum(sum(a["times"].values()) for a in items) / 60


def work_of(item):
    """Tokens of every model call: two runs of a question did the same work if these are equal."""
    return [(r["tokens"]["prompt_tokens"], r["tokens"]["answer_tokens"]) for r in item["rounds"]] + [(item["tokens"].get("prompt_tokens"), item["tokens"].get("answer_tokens"))]


def fixes_table(agent, fixed):
    """The 3C run against the 3C.1 run."""
    o, f = agent["summary"]["overall"], fixed["summary"]["overall"]
    a, u, gold = f["answerable"], f["unanswerable"], f["with_gold_chunks"]
    reached = lambda run: sum(bool(r["retrieval"] and r["retrieval"]["gold_judged"]) for r in run["items"].values())
    used = lambda group: f"{group['rounds_used']['1']} / {group['rounds_used']['2']} / {group['rounds_used']['3']}"
    kinds = lambda group: ", ".join(str(n) for n in problems_of(group).values())
    work_o, work_f = judge_work(agent), judge_work(fixed)
    rows = [("Key facts found", f"{o['fact_share']:.0%}", f"{f['fact_share']:.0%}"),
            ("Answers with every key fact, by matching", f"{share(o, 'all_facts', a)} of {a}", f"{share(f, 'all_facts', a)} of {a}"),
            ("Answers with every key fact, checked by hand", f"{len(complete(agent, 'agent'))} of {a}", f"{len(complete(fixed, 'agent-3c1'))} of {a}"),
            ("Correct refusals", f"{o['correct_refusals']} of {u}", f"{f['correct_refusals']} of {u}"),
            ("Wrong refusals", f"{o['wrong_refusals']} of {a}", f"{f['wrong_refusals']} of {a}"),
            ("The right chunk reached the Judge", f"{reached(agent)} of {gold}", f"{reached(fixed)} of {gold}"),
            ("The writer saw the right chunk", f"{share(o, 'recall_at_8', gold)} of {gold}", f"{share(f, 'recall_at_8', gold)} of {gold}"),
            ("Citation check passed", f"{share(o, 'check_passed', a)} of {a}", f"{share(f, 'check_passed', a)} of {a}"),
            ("Failures: search, Judge, writer", kinds(o), kinds(f)),
            ("Questions that took 1 / 2 / 3 rounds", used(o), used(f)),
            ("Rounds of the Judge", str(work_o[0]), str(work_f[0])),
            ("Chunks the Judge read", str(work_o[1]), str(work_f[1])),
            ("Tokens of the Judge", f"{work_o[2]:,}", f"{work_f[2]:,}"),
            ("Measured time, all 32 questions", f"{minutes(agent['items'].values()):.0f} min", f"{minutes(fixed['items'].values()):.0f} min"),
            ("Median time per question", f"{o['seconds_median']:.0f} s", f"{f['seconds_median']:.0f} s")]
    return "\n".join(["| Measure | 3C | 3C.1 |", "|---|---:|---:|"] + [f"| {m} | {x} | {y} |" for m, x, y in rows])


def add_fixes_section(add, agent, fixed):
    o, f = agent["summary"]["overall"], fixed["summary"]["overall"]
    same_answer = [i for i, a in fixed["items"].items() if a["answer"] == agent["items"][i]["answer"]]
    same_work = [i for i, a in fixed["items"].items() if work_of(a) == work_of(agent["items"][i])]
    ratios = [sum(fixed["items"][i]["times"].values()) / sum(agent["items"][i]["times"].values()) for i in same_work]
    work_o, work_f = judge_work(agent), judge_work(fixed)
    add("## Phase 3C.1: the two fixes\n")
    add(FIXES.format(o_wr=o["wrong_refusals"], f_wr=f["wrong_refusals"], o_facts=o["fact_share"], f_facts=f["fact_share"]) + "\n")
    add(fixes_table(agent, fixed) + "\n")
    add(f"**What changed is what the fixes changed.** {len(same_answer)} of the 32 answers are word for word the same as in 3C, because the model repeats itself when its input is the same. {32 - len(same_answer)} differ, and I read each of them:\n")
    add("| Question | Rounds | What happened | How it ended |")
    add("|---|---:|---|---|")
    for question, rounds, what, ended in CHANGED:
        add(f"| {question} | {rounds} | {what} | {ended} |")
    add()
    add(FIXES_NOTES.format(stops=f["stopped_by_code"], r_f=work_f[0], r_o=work_o[0], token_drop=1 - work_f[2] / work_o[2], t_f=minutes(fixed["items"].values()), t_o=minutes(agent["items"].values()),
                           n_same=len(same_work), same_o=minutes(agent["items"][i] for i in same_work), same_f=minutes(fixed["items"][i] for i in same_work), low=min(ratios), high=max(ratios)) + "\n")
    add("The rest of this report describes the Phase 3C run as it was measured, before these fixes. Only \"How the agent works\" and \"What I'd try next\" are up to date.\n")


def trace_block(add, record, note):
    add("```")
    for line in trace_lines(record["rounds"]):
        add(line)
    add("```\n")
    add("> " + record["answer"].replace(note, "").strip().replace("\n\n", "\n>\n> ").replace("\n**", "\n> **") + "\n")


def main():
    one, agent, fixed = find_run(ONE_SHOT), find_run(AGENT), find_run(AGENT_FIXED)
    if not one or not agent or not fixed:
        raise SystemExit("A run is missing: see the top of this script")
    o, g, f = one["summary"]["overall"], agent["summary"]["overall"], fixed["summary"]["overall"]
    items = agent["items"]
    note = closing_note()
    a_facts = {i: r["score"]["fact_share"] for i, r in items.items() if r["answerable"]}
    o_facts = {i: one["items"][i]["score"]["fact_share"] for i in a_facts}
    better, worse = [i for i in a_facts if a_facts[i] > o_facts[i]], [i for i in a_facts if a_facts[i] < o_facts[i]]
    multi = [i for i, r in items.items() if len(r["rounds"]) > 1]
    extra = sum(sum(r["seconds"].values()) for a in items.values() for r in a["rounds"][1:]) / 60
    total = sum(sum(a["times"].values()) for a in items.values()) / 60
    judged = [r for r in items.values() if r["retrieval"] and r["retrieval"]["gold_judged"]]
    first_rounds = [a["rounds"][0] for a in items.values()]
    kinds = problems_of(g)
    new_items = fixed["items"]
    fixed_kinds = problems_of(f)
    fixed_times = {}
    for record in new_items.values():
        for step, seconds in record["times"].items():
            fixed_times[step] = fixed_times.get(step, 0) + seconds
    new_shown = {i: [c for r in a["rounds"] for c in r["chunks"]] for i, a in new_items.items()}

    claims = {"3C.1: the counts behind FIXES": (len(complete(agent, "agent")), len(complete(fixed, "agent-3c1")), g["correct_refusals"], f["correct_refusals"], g["wrong_refusals"], f["wrong_refusals"]) == (13, 13, 5, 5, 2, 1),
              "the three wrong answers on each system say what the report says": "πέντε τουλάχιστον ημέρας" in items["sector-01"]["answer"] and "δεν απαιτεί προηγούμενη άδεια" in items["sector-02"]["answer"] and "έγινε η καταβολή της αποζημίωσης" in items["single-10"]["answer"]
              and "21 Αυγούστου" in one["items"]["single-27"]["answer"] and "δεν υπερβαίνει το ανώτατο χρονικό διάστημα" in one["items"]["single-17"]["answer"] and "επιφύλαξη" not in one["items"]["lookup-01"]["answer"],
              "3C.1: the answers that changed are the six in CHANGED": {i for i, a in new_items.items() if a["answer"] != items[i]["answer"]} == {q.strip("`") for q, *_ in CHANGED},
              "3C.1: no question lost a key fact, only single-09 gained": {i for i, a in new_items.items() if a["answerable"] and a["score"]["fact_share"] != items[i]["score"]["fact_share"]} == {"single-09"} and new_items["single-09"]["score"]["fact_share"] > items["single-09"]["score"]["fact_share"],
              "3C.1: the stop rule fired on these five": {i for i, a in new_items.items() if any(r["stopped_by_code"] for r in a["rounds"])} == {"single-09", "single-27", "vocab-01", "vocab-03", "refuse-06"},
              "3C.1: single-09's right chunk came from rank 15 in round 2": new_items["single-09"]["retrieval"]["gold_first_round"] == 2 and new_items["single-09"]["retrieval"]["rank"] == 15 and any(c["id"] == "glc-41850-011" and c["source"] == "question, rank 15" for c in new_shown["single-09"]),
              "3C.1: single-09 says void, doesn't name the law, two quotes fail": "άκυρη" in new_items["single-09"]["answer"] and "2112" not in new_items["single-09"]["answer"] and len(new_items["single-09"]["check"]["failures"]) == 2,
              "3C.1: vocab-03's writer has the right chunk third and doesn't cite it": next(c["n"] for c in new_items["vocab-03"]["chunks"] if c["id"] == "glc-35409-004") == 3 and 3 not in new_items["vocab-03"]["check"]["citations"],
              "3C.1: refuse-06 refused by the writer": new_items["refuse-06"]["score"]["refused"] and not new_items["refuse-06"]["refused_by_judge"] and items["refuse-06"]["refused_by_judge"],
              "3C.1: the ranks further reading can't reach": (new_items["vocab-01"]["retrieval"]["rank"], new_items["reference-01"]["retrieval"]["rank"], new_items["lookup-01"]["retrieval"]["rank"]) == (19, 27, 30),
              "3C.1: 4 chunks more in round 2 on the 6 that reach it": {i: len(a["rounds"][1]["chunks"]) - len(items[i]["rounds"][1]["chunks"]) for i, a in new_items.items() if len(a["rounds"]) > 1} == dict.fromkeys(("single-09", "sector-03", "reference-01", "refuse-04", "refuse-06", "lookup-01"), 4),
              "3C.1: its claims of a missing law are among the 11 checked ones": {law for a in new_items.values() for law in a["laws_missing"]} <= {law for a in items.values() for law in a["laws_missing"]},
              "the counts behind RESULT": (len(complete(one, "one-shot")), len(complete(agent, "agent")), g["correct_refusals"], g["wrong_refusals"], o["correct_refusals"], o["wrong_refusals"]) == (9, 13, 5, 2, 4, 0),
              "the right chunk only ever arrives in round 1": {r["retrieval"]["gold_first_round"] for r in judged} == {1},
              "the 9 questions in ROUNDS": {i.strip("`") for i, *_ in ROUNDS} == set(multi),
              "the 3C run is untouched by the fixes": not any("stopped_by_code" in r for a in items.values() for r in a["rounds"]),
              "sector-01 says 5 days": "πέντε τουλάχιστον ημέρας" in items["sector-01"]["answer"] and items["sector-01"]["score"]["fact_share"] == 1,
              "vocab-03: right chunk first in round 1, Judge saw it, writer didn't": (items["vocab-03"]["retrieval"]["rank"], items["vocab-03"]["retrieval"]["gold_first_round"], items["vocab-03"]["retrieval"]["in_context"]) == (1, 1, False),
              "the one-shot cites another chunk on refuse-06": "glc-13205-007" in {c["id"] for c in one["items"]["refuse-06"]["chunks"] if c["n"] in one["items"]["refuse-06"]["check"]["citations"]},
              "reference-01 names five groups in round 1": sum(bool(v["only_for"]) for v in items["reference-01"]["rounds"][0]["verdicts"]) == 5,
              "refuse-06 answered by the one-shot, refused by the agent": items["refuse-06"]["score"]["refused"] and not one["items"]["refuse-06"]["score"]["refused"],
              "single-09 refused, names Ν. 2112/1920": items["single-09"]["refused_by_judge"] and "Ν. 2112/1920" in items["single-09"]["answer"],
              "single-15 replaced two older rules": sum(bool(v["replaced_by"]) for v in items["single-15"]["rounds"][0]["verdicts"]) == 2,
              "refuse-01 refused in one round": len(items["refuse-01"]["rounds"]) == 1 and "Ν. 4808/2021" in items["refuse-01"]["answer"],
              "the three who searched on with a right chunk": {i for i, a in items.items() for r in a["rounds"] if r["decision"] == "search_again" and any(v["relevance"] == "relevant" and v["applies"] == "yes" for v in r["verdicts"])} == {"single-27", "vocab-01", "vocab-03"},
              "11 claims of a missing law": sum(len(a["laws_missing"]) for a in items.values()) == 11}
    broken = [claim for claim, holds in claims.items() if not holds]
    if broken:
        raise SystemExit("These claims in the report no longer hold, redo its text:\n- " + "\n- ".join(broken))

    lines = []

    def add(text=""):
        lines.append(text)

    add("# Agent report: the agent loop with LangGraph (Phases 3C and 3C.1)\n")
    add("Phase 3C joins the pieces into an agent: search, a Judge that decides what can be used, more searching if it asks, then the writer. This report measures it with full "
        "answers on the dev questions, against the one-shot from Phase 3A (qwen3, semantic search, limit 2, with the repeat filter from Phase 3B). Phase 3C.1 then made two fixes, which "
        "come first because that's the agent as it is now. This file is generated by "
        "[`scripts/agent_report.py`](../scripts/agent_report.py) from the stored runs in [`eval/results/`](../eval/results/). Don't edit it by hand.\n")

    add_fixes_section(add, agent, fixed)

    add("## The result of Phase 3C\n")
    add(RESULT.format(a_hand=len(complete(agent, "agent")), o_hand=len(complete(one, "one-shot")), n=g["answerable"], o_facts=o["fact_share"], a_facts=g["fact_share"], a_cr=g["correct_refusals"], o_cr=o["correct_refusals"],
                      u=g["unanswerable"], a_wr=g["wrong_refusals"], o_wr=o["wrong_refusals"], a_time=g["seconds_median"], o_time=o["seconds_median"], judged=len(judged), gold=g["with_gold_chunks"],
                      never=g["with_gold_chunks"] - len(judged), multi=len(multi), extra=extra, total=total, approved=sum(len(r["approved"]) for r in first_rounds), shown=sum(len(r["chunks"]) for r in first_rounds),
                      a_chunks=statistics.mean(len(a["chunks"]) for a in items.values() if not a["refused_by_judge"]), o_chunks=statistics.mean(len(r["chunks"]) for r in one["items"].values()),
                      better=len(better), worse=len(worse), chance=chance_of_split(len(better), len(worse))) + "\n")

    add("## The numbers\n")
    add(overall_table(one, agent, o, g) + "\n")
    add(f"**Why two rows for complete answers.** Key facts are matched without a model, and that can't read meaning. So I read every answer scored as complete on either system, and in Phase 4A I read them again by one rule: an answer fails if it states a key fact wrong anywhere, short answer included. "
        "Three fail on each system. On the agent: `sector-01` (5 days instead of 30), `sector-02` (it says no permit is needed, and the chunk requires one) and `single-10` (the six months start from the wrong date). On the one-shot: `single-17` (its short answer turns the exception around), "
        "`single-27` (it puts the Dormition on 21 August) and `lookup-01` (\"subject to article 3\" isn't there: the matcher took a list number for it). **This report said 15 against 12 until then:** my first reading found only `sector-01`, which was too generous. By the same rule the one-shot of Phase 2 (bge-m3 and RRF) has 6 of 26.\n")
    add(f"**Where the two differ.** The writer saw the right chunk for {share(g, 'recall_at_8', g['with_gold_chunks'])} questions on both, but not the same ones. The agent gains `sector-05`, because limit 4 lets the "
        "chunk through. It loses `vocab-03`, because the Judge rejected it. Key facts are up on " + ", ".join(f"`{i}`" for i in better) + "; down on " + ", ".join(f"`{i}`" for i in worse) + ".\n")
    add(f"**Failures, by who caused them.** The agent: search {kinds['search']}, Judge {kinds['judge']}, writer {kinds['writer']} (the code gives {g['agent_problems']['writer']}, and the three wrong answers above add the rest). The one-shot, which has no Judge: search "
        f"{o['search_problems']}, reading {o['reading_problems']}, plus its three wrong answers.\n")
    times = {}
    for record in items.values():
        for step, seconds in record["times"].items():
            times[step] = times.get(step, 0) + seconds
    judge_share = times["judge"] / sum(times.values())
    add(f"**Where the time goes.** All 32 questions took the agent {total:.0f} minutes of measured time and the one-shot {sum(sum(r['times'].values()) for r in one['items'].values()) / 60:.0f}. The Judge takes {times['judge'] / 60:.0f} of those {total:.0f}, "
        f"the writer {times['model answer'] / 60:.0f}, the Query Enhancer {times['enhancer'] / 60:.0f}, and search less than one. A round of the Judge takes a median of {statistics.median(r['seconds']['judge'] for a in items.values() for r in a['rounds']):.0f} s.\n")
    add("**Per category.** Each cell shows one-shot → agent. Every fact is by matching, so it counts the wrong answers above as complete. Most categories have only 2 to 5 questions.\n")
    add(category_table(one, agent) + "\n")

    add("## What the extra rounds did\n")
    add("| Question | Rounds | Compared with stopping earlier | What happened |")
    add("|---|---:|---|---|")
    for question, rounds, verdict, what in ROUNDS:
        add(f"| {question} | {rounds} | {verdict} | {what} |")
    add()
    add("**`lookup-01`** is a problem in our data, found in Phase 2. Article 2 of Ν. 1837/1989 sits inside the chunk labelled \"Άρθρο 18\". So the Judge, reading labels honestly, rejects everything. The one-shot "
        "doesn't look at labels, and it writes the rule down, with a quote from another article, so it scores better for being less careful.\n")

    add("## Three traced examples\n")
    add("These are the output of `python -m labour_rag.agent \"…\" --trace`, from the stored run.\n")
    add("### 1. The second round rescuing an answer: none exists in this run\n")
    add("No question got a right chunk in round 2 or 3. The closest is `refuse-06`, where more rounds led to a correct refusal, and the one-shot answered from a chunk on family allowances. It isn't a real rescue: the "
        "later rounds found nothing, and the Judge changed its mind in the round when it could no longer ask for more. Phase 3C.1 got the first real one, `single-09`, traced in "
        "[How a question is answered](how-a-question-is-answered.md).\n")
    add(f"**Question:** {items['refuse-06']['question']}\n")
    trace_block(add, items["refuse-06"], note)
    add("### 2. A correct refusal\n")
    add("One round and 44 s. The law is from 2021, the data stops in 1999, and the code says so itself: the model can't invent anything here.\n")
    add(f"**Question:** {items['refuse-01']['question']}\n")
    trace_block(add, items["refuse-01"], note)
    add("### 3. A failure\n")
    add("Round 1 has the right chunk, first in the list, and approves it. The Judge searches on anyway and rejects it in round 2.\n")
    add(f"**Question:** {items['vocab-03']['question']}\n")
    trace_block(add, items["vocab-03"], note)

    add("## The five most instructive failures\n")
    for number, (item, label, title, why) in enumerate(FAILURES, 1):
        add(f"### {number}. `{item}`: {title}\n")
        add(f"**{label} problem.** {items[item]['question']}\n")
        add(why + "\n")

    add("## How the agent works\n")
    add("This is the frozen agent, after Phase 3C.1. [How a question is answered](how-a-question-is-answered.md) gives every rule in full.\n")
    add("```\nquestion\n   |\n   v\nsearch: the plain question, qwen3, limit 4, keyword places if it names a law or article\n   |\n   v\nJudge: one verdict per chunk, then answer, search again or refuse <-----+\n   |                  |                                                 |\n   |                  '--> search again (at most 3 rounds in all) ------+\n   |                       not if an approved chunk answers directly: the code writes instead\n   |                       round 2: the next 8 places on the plain list, the enhancer's phrasings,\n   |                                laws the Judge named, articles next to approved chunks\n   |                       round 3: what the Judge said was missing and the same phrasings,\n   |                                laws the Judge named, articles next to approved chunks\n   |\n   +--> write: approved chunks + the person's own question, then the citation check\n   '--> refuse: written by the code, names where the rule would be when known\n```\n")
    add("The numbers in this section are from the Phase 3C run.\n")
    add("- **The Judge** is one call to `ministral-3:8b` at temperature 0, with its instructions in [`prompts/judge.md`](../prompts/judge.md). For each chunk it gives relevant, partly or not relevant; whether it applies to this person; "
        "which group it's only for; and whether a newer act replaces it. A chunk is approved if it's relevant or partly, doesn't fail to apply, and isn't replaced.\n"
        "- **The code checks the Judge,** because a JSON schema fixes only the shape. A \"newer\" act must really be newer. A law it names must be cited in the chunks: the code dropped 31 that weren't, mostly the chunk's own act. The last round "
        "can't search again.\n"
        "- **A law that isn't in our data is mentioned** in the answer or the refusal, by the code. All 11 such claims in this run are true: I checked them against [missing-laws.md](missing-laws.md) and the chunks.\n"
        "- **The prompt's example is on a topic outside the test set,** and `tests/test_agent.py` checks that.\n"
        "- **It stays local.** LangGraph brings LangSmith, LangChain's tracing service, with it. It is switched off in the code. One question run with all outside connections blocked tried none.\n"
        "- **Each round is recorded** in the result: chunks, verdicts, reasons and time.\n")

    add("## What I'd try next\n")
    add(NEXT.format(writer=fixed_kinds["writer"], problems=sum(fixed_kinds.values()), judge_share=fixed_times["judge"] / sum(fixed_times.values())) + "\n")

    add("## What this doesn't show\n")
    add(LIMITS + "\n")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
