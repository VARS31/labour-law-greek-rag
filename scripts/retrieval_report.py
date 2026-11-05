"""Phase 3A: write docs/retrieval-report.md from the stored fusion runs.

    .venv/bin/python -I scripts/retrieval_report.py

The runs used the repeat filter as it was before Phase 3B, so they can't be repeated with today's code: commit 79de467 has
the code that made them. Retrieval only, on dev. The winner is worked out here and must be search.DEFAULT_FUSION. The words around the numbers are
hand-written (WHY_OLD_LOST, KEYWORD, SINGLE_15, LIMITS_OF_THIS and the text in main): the script stops if the claims it can
check stop holding, and all of them must be re-read whenever the runs change.
"""

import collections
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag import evaluate, search  # noqa: E402
from labour_rag.ask import closing_note  # noqa: E402
from labour_rag.citations import says_not_found  # noqa: E402
from scripts.eval_report import CATEGORY_TEXT, find_run  # noqa: E402

REPORT = ROOT / "docs/retrieval-report.md"
EMBEDDINGS = ("bge-m3", "qwen3-4b")
PLAIN = "qwen3-4b-plain"        # qwen3 without the query instruction: run for the winner only, to test the embedding rule
LIMITS = (2, 4)
DEFAULT_LIMIT = 2
DEFAULT_EMBEDDING = "bge-m3"
LABELS = {"rrf": "(a) RRF, equal weights (old default)",
          "weighted": "(b) RRF, semantic counts double",
          "semantic": "(c) Semantic only",
          "law-lookup": "(d) Semantic, keyword only if a law or article is named",
          "reserved": "(e) 6 places for semantic, then 2 for keyword"}
EMBEDDING_BAR = 3               # the owner's rule: qwen3 must win by at least this many questions
FIVE = ("vocab-06", "reference-01", "single-14", "single-17", "vocab-02")

WHY_OLD_LOST = """**Why the old way lost.** Our RRF uses the constant 60 and takes 50 chunks from each list. So a chunk found by \
both lists scores at least 2/110 = 0.0182, and the first chunk of one list scores 1/61 = 0.0164. Any chunk in both lists, even 50th \
in each, beat the first result of either list. Keyword search accepts any word of the question, so it finds a lot, and that pushed \
down what semantic search had ranked high. Doubling semantic's weight (b) helps but doesn't cure it: below semantic's rank 13, a \
chunk can still lose to one that is 50th in both lists."""

KEYWORD = """**Keyword search adds nothing here.** With bge-m3 and limit 2, (c), (d) and (e) bring the very same questions to the \
writer. That doesn't prove keyword search is useless. Dev has only 2 questions with a gold chunk that name a law, and those are the \
only ones where (d) can differ from (c). And `sector-02` is 2nd in keyword search but 20th in semantic search, so semantic search \
alone loses it. Keyword search stays in the code, and the agent in Phase 3 can use it as a separate tool."""

SINGLE_15 = """**A problem this change exposes: `single-15`.** The right chunk (Π.Δ. 176/1997, 16 weeks of maternity leave) is 2nd in \
semantic search, behind an older decision (Υ.Α. 12756/1989, 15 weeks). Their words overlap by 60%, and the repeat filter ignores \
numbers, so it calls them repeats and keeps whichever comes first. Under the old fusion the newer one came first. Now the writer gets \
15 weeks, where the expected answer is 16. So the filter can remove a newer law because it looks like the older one. I didn't change \
the filter, because this phase is about fusion, but it should be fixed before the agent relies on it."""

LIMITS_OF_THIS = """- **No answers were written.** More right chunks may not mean better answers: in Phase 2, limit 4 brought 3 more \
right chunks and no better answers. Only a run with the writer can show this.
- **The winner is flattered.** It was chosen on the same 27 questions it's measured on, and one question is about 4 points. The test \
questions weren't touched.
- **The baseline on test is still the old setup.** `2026-11-04_oneshot-limit2-test` used equal-weight RRF, and Phase 4 compares \
against those numbers. The new default has no test number, because the one-shot system has used its one run.
- **Refusals weren't measured.** Questions that must be refused have no gold chunk, so they don't count in any number above."""


def run_name(embedding, fusion, limit):
    return evaluate.config_name({"retrieval_only": True, "embedding": embedding, "fusion": fusion, "max_per_document": limit,
                                 "split": "dev"})


def grid():
    """Every (embedding, fusion, limit) the report needs."""
    combos = [(e, f, l) for e in EMBEDDINGS for f in search.FUSIONS for l in LIMITS]
    return combos + [(PLAIN, search.DEFAULT_FUSION, l) for l in LIMITS]


def pick_winner(delivered):
    """The rule: most right chunks delivered to the writer; within one question, the simpler way (search.FUSIONS is
    ordered simplest first)."""
    best = max(delivered.values())
    return next(f for f in search.FUSIONS if delivered[f] >= best - 1)


def count(group, key="recall_at_8"):
    """A share back to a number of questions."""
    return round(group[key] * group["with_gold_chunks"])


def arrived(run):
    return {i for i, r in run["items"].items() if r["retrieval"] and r["retrieval"]["in_context"]}


def chance_of_split(wins, losses):
    """How often a split this uneven happens by chance, if each question could go either way (two-sided sign test)."""
    total = wins + losses
    tail = sum(math.comb(total, i) for i in range(max(wins, losses), total + 1))
    return min(1.0, 2 * tail / 2 ** total)


def names(ids):
    return ", ".join(f"`{i}`" for i in sorted(ids)) or "none"


def main_table(runs, winner):
    head = ["Way of combining"] + [f"{e}, {x}" for e in ("bge-m3", "qwen3") for x in ("limit 2", "limit 4", "top 50", "MRR")]
    lines = ["| " + " | ".join(head) + " |", "|---|" + "---:|" * (len(head) - 1)]
    for fusion, label in LABELS.items():
        cells = []
        for embedding in EMBEDDINGS:
            two, four = (runs[embedding, fusion, limit]["summary"]["overall"] for limit in LIMITS)
            cells += [count(two), count(four), count(two, "recall_at_50"), f"{two['mrr']:.2f}"]
        name = f"**{label}**" if fusion == winner else label
        lines.append(f"| {name} | " + " | ".join(map(str, cells)) + " |")
    return "\n".join(lines)


def category_table(runs, embedding):
    """Per category, for every way of combining: limit 2 / limit 4 / top 50 / MRR."""
    lines = ["| Category | Questions | " + " | ".join(f.split(" ")[0] for f in LABELS.values()) + " |",
             "|---|---:|" + "---:|" * len(LABELS)]
    for category, (label, _, _) in CATEGORY_TEXT.items():
        cells, questions = [], 0
        for fusion in LABELS:
            two, four = (runs[embedding, fusion, limit]["summary"]["by_category"].get(category) for limit in LIMITS)
            if not two or not two["with_gold_chunks"]:
                break
            questions = two["with_gold_chunks"]
            cells.append(f"{count(two)} / {count(four)} / {count(two, 'recall_at_50')} / {two['mrr']:.2f}")
        if cells:
            lines.append(f"| {label} | {questions} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def why_missed(retrieval):
    if retrieval["removed_as"] == "same document":
        return "Removed: its document already had 2 chunks among the 8"
    if retrieval["removed_as"] == "near-duplicate":
        return "Removed as a repeat of a chunk already kept"
    if retrieval["rank"]:
        return f"Ranked {retrieval['rank']}: the 8 places were filled first"
    return "Not in the top 50"


def misses_table(run):
    lines = ["| Question | Category | Semantic rank | Keyword rank | Why it doesn't arrive |", "|---|---|---:|---:|---|"]
    for item, record in run["items"].items():
        retrieval = record["retrieval"]
        if retrieval and not retrieval["in_context"]:
            lines.append(f"| `{item}` | {CATEGORY_TEXT[record['category']][0]} | {retrieval['semantic_rank'] or '-'} | "
                         f"{retrieval['keyword_rank'] or '-'} | {why_missed(retrieval)} |")
    return "\n".join(lines)


def arrival(run, item):
    retrieval = run["items"][item]["retrieval"]
    rank = retrieval["rank"] or "over 50"
    return f"{'**yes**' if retrieval['in_context'] else 'no'} (rank {rank})"


def five_table(old, new, new_limit4, new_qwen):
    lines = ["| Question | What it asks | Old way, rank | New default | New, limit 4 | New, qwen3 |", "|---|---|---|---|---|---|"]
    for item in FIVE:
        lines.append(f"| `{item}` | {old['items'][item]['question']} | {arrival(old, item)} | {arrival(new, item)} | "
                     f"{arrival(new_limit4, item)} | {arrival(new_qwen, item)} |")
    return "\n".join(lines)


def refusal_changes(answer_runs):
    """(table rows, one row per run with counts before and now). "Before" means the exact words only, as the code then
    checked; an answer that wasn't a refusal also failed the check if it cited nothing."""
    note, changes, totals = closing_note(), [], []
    for label, run in answer_runs:
        records = run["items"].values()
        flipped = 0
        for record in records:
            before = says_not_found(record["answer"].replace(note, " "))
            now = record["score"]["refused"]
            if before == now:
                continue
            flipped += 1
            check_before = record["check"]["ok"] and (before or bool(record["check"]["citations"]))
            passed = "same" if check_before == record["check"]["ok"] else ("failed, now passes" if record["check"]["ok"] else "passed, now fails")
            kind = "correct refusal" if not record["answerable"] else "wrong refusal"
            changes.append(f"| {label} | `{record['id']}` | {'no' if record['answerable'] else 'yes'} | {kind} | {passed} |")
        overall = run["summary"]["overall"]
        wrong = overall["wrong_refusals"]
        wrong_before = wrong - sum(r["answerable"] and r["score"]["refused"]
                                   and not says_not_found(r["answer"].replace(note, " ")) for r in records)
        correct = overall["correct_refusals"]
        correct_before = correct - sum(not r["answerable"] and r["score"]["refused"]
                                       and not says_not_found(r["answer"].replace(note, " ")) for r in records)
        totals.append(f"| {label} | {flipped} | {correct_before} → {correct} of {overall['unanswerable']} | "
                      f"{wrong_before} → {wrong} of {overall['answerable']} |")
    return changes, totals


def main():
    runs = {}
    for embedding, fusion, limit in grid():
        runs[embedding, fusion, limit] = find_run(run_name(embedding, fusion, limit))
    missing = [run_name(*key) for key, run in runs.items() if not run]
    if missing:
        raise SystemExit(f"These runs are missing: {', '.join(missing)}")

    n = runs[DEFAULT_EMBEDDING, "rrf", DEFAULT_LIMIT]["summary"]["overall"]["with_gold_chunks"]
    columns = {(e, l): {f: count(runs[e, f, l]["summary"]["overall"]) for f in search.FUSIONS} for e in EMBEDDINGS for l in LIMITS}
    winner = pick_winner(columns[DEFAULT_EMBEDDING, DEFAULT_LIMIT])
    if winner != search.DEFAULT_FUSION:
        raise SystemExit(f"The rule picks {winner}, but search.DEFAULT_FUSION is {search.DEFAULT_FUSION}: redo the default and this report")
    other_columns = {key: pick_winner(value) for key, value in columns.items()}
    if set(other_columns.values()) != {winner}:
        raise SystemExit(f"The winner differs between columns: {other_columns}. Redo the text of this report")

    def run(embedding=DEFAULT_EMBEDDING, fusion=winner, limit=DEFAULT_LIMIT):
        return runs[embedding, fusion, limit]

    old, new = run(fusion="rrf"), run()
    gains, losses = arrived(new) - arrived(old), arrived(old) - arrived(new)
    if {"single-15", "sector-02"} != losses or new["items"]["single-15"]["retrieval"]["removed_as"] != "near-duplicate":
        raise SystemExit("The losses against the old way changed: redo SINGLE_15 and KEYWORD")
    if not arrived(run(fusion="law-lookup")) == arrived(run(fusion="reserved")) == arrived(new):
        raise SystemExit("(c), (d) and (e) no longer bring the same questions: redo KEYWORD")
    reasons = collections.Counter(why_missed(r["retrieval"]).split(":")[0].split(" ")[0] for r in new["items"].values()
                                  if r["retrieval"] and not r["retrieval"]["in_context"])
    by_limit = sum(r["retrieval"]["removed_as"] == "same document" for r in new["items"].values() if r["retrieval"])
    by_repeat = sum(r["retrieval"]["removed_as"] == "near-duplicate" for r in new["items"].values() if r["retrieval"]
                    and not r["retrieval"]["in_context"])
    by_rank = sum(reasons.values()) - by_limit - by_repeat

    lines = []

    def add(text=""):
        lines.append(text)

    add("# Retrieval report: fixing the fusion step (Phase 3A)\n")
    add("Phase 2 found that search often finds the right chunk and then loses it when the semantic and keyword lists are "
        "combined. This phase tries five ways of combining them. Retrieval only, on the dev questions: no writer, no prompt "
        "changes. This file is generated by [`scripts/retrieval_report.py`](../scripts/retrieval_report.py) from the stored runs in "
        "[`eval/results/`](../eval/results/). Don't edit it by hand.\n")
    add("Phase 3B has since made qwen3 the default, on the project owner's decision, and fixed the repeat filter described below: "
        "see [enhancer-report.md](enhancer-report.md). The numbers here are from before those changes.\n")

    add("## The result\n")
    add(f"**Winner: (c), semantic search alone.** With bge-m3 and limit 2, the right chunk now reaches the writer for "
        f"**{count(new['summary']['overall'])} of {n}** dev questions, up from {count(old['summary']['overall'])} of {n}. (d) and "
        "(e) reach the same number, and the rule says that within one question the simpler way wins. Semantic search alone is the "
        "new default. The old way stays selectable with `--fusion rrf`, in `labour_rag.ask` and `labour_rag.evaluate`.\n")
    add(WHY_OLD_LOST + "\n")

    add("## The table\n")
    add(f"Limit 2 and limit 4 count how many of the {n} questions get their right chunk to the writer, after repeat removal and "
        "the per-document limit (recall@8). Top 50 is the same count for the first 50 results (recall@50). MRR says how high the "
        "right chunk ranks. Those two don't depend on the limit.\n")
    add(main_table(runs, winner) + "\n")
    add("(e) is my own variant, chosen before any of these runs: keyword search can add what semantic missed on any question, but "
        "can't push out what semantic ranked highest.\n")
    limit4 = columns[DEFAULT_EMBEDDING, 4]
    add(f"The rule gives the same winner in all four columns. The closest case is bge-m3 with limit 4, where (e) reaches "
        f"{limit4['reserved']} and (c) {limit4['semantic']}: one question apart, so the simpler one wins. **The limit stays at 2.** "
        "It wasn't part of this decision, and Phase 2 found no better answers with limit 4.\n")
    add(KEYWORD + "\n")
    add("**Per category.** Each cell shows limit 2 / limit 4 / top 50 / MRR.\n")
    add("bge-m3:\n")
    add(category_table(runs, "bge-m3") + "\n")
    add("qwen3:\n")
    add(category_table(runs, "qwen3-4b") + "\n")

    add("## What moved\n")
    add(f"Compared with the old way, on bge-m3 and limit 2, the right chunk now arrives for {len(gains)} more questions "
        f"({names(gains)}) and no longer arrives for {len(losses)} ({names(losses)}).\n")
    add(SINGLE_15 + "\n")
    add(f"**The {sum(reasons.values())} questions that still miss.** The per-document limit removes {by_limit}, the repeat filter "
        f"removes {by_repeat}, and {by_rank} rank too low. The rewriter in Phase 3 is aimed at that last group.\n")
    add(misses_table(new) + "\n")

    add("## The five questions from the evaluation report\n")
    if {i for i in FIVE if not new["items"][i]["retrieval"]["in_context"]} != {"single-17"} or "reference-01" in arrived(run(embedding="qwen3-4b")):
        raise SystemExit("The five questions moved: redo the text of this section")
    add("Phase 2 named these as questions that semantic search found and fusion lost. **"
        f"{sum(new['items'][i]['retrieval']['in_context'] for i in FIVE)} of the 5 now reach the writer** with the new default. "
        "The one that doesn't, `single-17`, is no longer lost to fusion: it's at rank 5 and the limit of 2 per document removes it. "
        "It arrives with limit 4 or with qwen3. With qwen3 `reference-01` is lost instead.\n")
    add(five_table(old, new, run(limit=4), run(embedding="qwen3-4b")) + "\n")

    add("## Does qwen3 beat bge-m3?\n")
    difference = {limit: count(run(embedding="qwen3-4b", limit=limit)["summary"]["overall"])
                  - count(run(limit=limit)["summary"]["overall"]) for limit in LIMITS}
    if min(difference.values()) < EMBEDDING_BAR:
        raise SystemExit(f"qwen3 no longer clears the bar in every setting: {difference}. Redo this section")
    qwen = run(embedding="qwen3-4b")
    wins, drops = arrived(qwen) - arrived(new), arrived(new) - arrived(qwen)
    plain2, plain4 = (count(run(embedding=PLAIN, limit=limit)["summary"]["overall"]) for limit in LIMITS)
    add(f"**Yes. With the winning fusion, qwen3 beats bge-m3 by {difference[2]} of {n} questions at limit 2 "
        f"({count(qwen['summary']['overall'])} against {count(new['summary']['overall'])}) and by {difference[4]} at limit 4 "
        f"({count(run(embedding='qwen3-4b', limit=4)['summary']['overall'])} against {count(run(limit=4)['summary']['overall'])}). "
        f"That clears the bar of {EMBEDDING_BAR}.** The default stays bge-m3: this choice is the project owner's.\n")
    add(f"- **Which questions, at limit 2:** it gains {names(wins)} and loses {names(drops)}.")
    add(f"- **How sure:** a split of {len(wins)} to {len(drops)} would happen by chance about "
        f"{chance_of_split(len(wins), len(drops)):.0%} of the time. That's suggestive, on a small sample.")
    add(f"- **Without the query instruction:** {plain2} at limit 2 and {plain4} at limit 4, so the result doesn't depend on it.")
    add(f"- **Cost:** the embedding is already done, and took about 2.5 hours. A search takes about "
        f"{qwen['summary']['overall']['seconds_median']:.2f} s instead of {new['summary']['overall']['seconds_median']:.2f} s. New "
        "chunks in Phase 5 would be embedded at the same slow speed, about 30 times slower than bge-m3.")
    add("- **Not measured:** whether the writer gives better answers with it.\n")

    add("## Refusal detection\n")
    add("An answer now counts as a refusal if it says near its start that the answer isn't in the sources, in the prompt's words "
        "(\"Δεν βρέθηκε\") or in others (\"δεν αναφέρεται στα αποσπάσματα\", \"τα αποσπάσματα δεν αναφέρουν\"). A sentence that goes "
        "on with \"αλλά\" doesn't count, because it gives an answer after all, and neither does a missing detail later in an "
        "answer. The rule was written from dev answers only. All stored answers were scored again.\n")
    answer_runs = [("Dev, limit 2", find_run("oneshot-limit2-dev")), ("Dev, limit 4", find_run("oneshot-limit4-dev")),
                   ("Test, limit 2", find_run("oneshot-limit2-test"))]
    changes, totals = refusal_changes(answer_runs)
    add("| Run | Answers that changed | Correct refusals | Wrong refusals |")
    add("|---|---:|---:|---:|")
    for row in totals:
        add(row)
    add()
    add("| Run | Question | Should it be refused? | Now counts as | Citation check |")
    add("|---|---|---|---|---|")
    for row in changes:
        add(row)
    add()
    add("`lookup-01` wrote «Το άρθρο 2 του Ν. 1837/1989 δεν αναφέρεται στα αποσπάσματα». It had no citation, so it used to fail the "
        "citation check as an answer that cites nothing. That's why the check on dev goes from 10 to 11 of 26. `lookup-02` is a test "
        "question, so I didn't read its answer. Its numbers fit a refusal (0 of 2 key facts, right chunk not among the 8), but only "
        "a person reading it can confirm that. Nothing else in the past runs changes, and the eight Phase 1C answers don't either. "
        "[`docs/eval-report.md`](eval-report.md) now shows these numbers.\n")

    add("## Test guard\n")
    add("The test split now runs once per named system instead of once in total, and `eval/test_runs.json` records who used it:\n")
    add("| System | Its run | Started |")
    add("|---|---|---|")
    for system, claim in json.loads(evaluate.TEST_RUNS.read_text(encoding="utf-8")).items():
        add(f"| {system} | `{claim['run']}` | {claim['started']} |")
    add()
    add("A second run for the same system is refused. An interrupted run may continue, but not with other settings. The agent isn't "
        "a choice for `--system` yet. Phase 4 adds it, so its one run can't be used up by accident on the one-shot code.\n")

    add("## What this doesn't show\n")
    add(LIMITS_OF_THIS + "\n")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
