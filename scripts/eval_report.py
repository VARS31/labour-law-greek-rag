"""Phase 2: write docs/eval-report.md from the stored runs in eval/results/.

Needs no database and no model. The numbers come from the runs. The hand-written parts (OVERALL, COMMENT_B, COMMENT_C,
TEST_COMMENT, FAILURES, NEXT, HAND_FACTS) must be redone whenever the runs change: the script stops if a quote in
FAILURES is no longer in its answer.

Usage: .venv/bin/python -I scripts/eval_report.py
"""

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag.key_facts import MIN_WORD_SHARE  # noqa: E402

RESULTS = ROOT / "eval/results"
QUESTIONS = ROOT / "eval/questions.jsonl"
REPORT = ROOT / "docs/eval-report.md"
MISSING_LAWS = ROOT / "docs/missing-laws.md"
STATS_QWEN = ROOT / "data/processed/embedding_stats_qwen3_4b.json"
STATS_BGE = ROOT / "data/processed/embedding_stats.json"

CATEGORY_TEXT = {
    "single_source": ("Answerable from one place",
                      "One article answers it. The everyday way to use the system.",
                      "Πόσες ώρες ξεκούραση πρέπει να έχω τουλάχιστον μέσα σε κάθε εικοσιτετράωρο;"),
    "sector_trap": ("Sector trap",
                    "A general rule and a rule for one group compete, and only one fits the question.",
                    "Είμαι εργάτης σε εργοστάσιο εδώ και έξι χρόνια. Πόσες μέρες πριν πρέπει να με ειδοποιήσουν για απόλυση;"),
    "vocabulary": ("Vocabulary mismatch",
                   "The question uses everyday words that the law doesn't use.",
                   "Πόσα ένσημα χρειάζομαι για να πάρω ταμείο ανεργίας;"),
    "follow_reference": ("Follow a reference",
                         "The chunk points to another law. Sometimes that law is in our data, sometimes not.",
                         "Δουλεύω σε εργοστάσιο και κάνω υπερωρίες. Με τι ποσοστό αυξάνεται το ωρομίσθιό μου;"),
    "must_refuse": ("Must be refused",
                    "Laws from after 1999, or topics outside labour law. The right answer is \"Δεν βρέθηκε…\".",
                    "Τι προβλέπει ο Ν. 4808/2021 για την ψηφιακή κάρτα εργασίας;"),
    "exact_lookup": ("Exact law lookup",
                     "The question names a law and sometimes an article.",
                     "Τι λέει το άρθρο 2 του Ν. 1837/1989;"),
}

# My own reading of the 32 baseline dev answers, fact by fact (Y = the fact is there), to see how far the automatic
# matching can be trusted. A fact from the wrong law or from outside knowledge still counts as there: whether the
# source was right is measured apart.
HAND_FACTS = {
    "lookup-01": "nnn", "lookup-03": "nYY", "reference-02": "YYn", "sector-01": "nn", "sector-02": "YYY",
    "sector-03": "YYY", "sector-05": "nn", "single-01": "YYY", "single-02": "YYn", "single-09": "nn", "single-10": "Yn",
    "single-11": "YYY", "single-14": "nnn", "single-15": "YYY", "single-17": "Ynn", "single-18": "nYY",
    "single-21": "nnn", "single-23": "YYY", "single-26": "YYY", "single-27": "YYYY", "single-29": "Yn",
    "single-32": "Yn", "vocab-01": "nnn", "vocab-02": "Ynn", "vocab-03": "nn", "vocab-06": "nn",
}

OVERALL = """**The baseline is far from good enough, and now we know by how much.** On the test split the right chunk reached \
the model for {t_r8} of {t_gold} questions, and {t_full} of {t_ans} answerable questions got every key fact. The model \
refused {t_cr} of the {t_un} questions it should have refused, and wrongly refused {t_wr} it could have answered.

- **Search and reading fail about equally often.** Over dev and test together, {search} answers fell short because the \
right chunk never arrived and {reading} because the model misused what it had, or answered when it should have refused.
- **Search usually finds the chunk but doesn't deliver it.** On dev the right chunk is in the top 50 for {d_r50} of \
{d_gold} questions, but among the 8 for only {d_r8}.
- **Hybrid search, as built, is the weak link.** Semantic search alone has the right chunk in its top 8 for {d_s8} of \
{d_gold} dev questions. Keyword search has it in its top 50 for only {d_k50}, and fusion then pushes down much of what \
semantic search found. This number isn't a fair race yet, because semantic's top 8 still contains repeats, but the gap is \
large. Phase 1B had already seen a sign of this.
- **Vocabulary mismatches fail almost completely on dev.** None of the 4 got the right chunk among the 8.
- **The citation check doesn't tell good answers from bad.** On dev, {pass_full} of the {pass_all} answers that passed it \
had every key fact, against {fail_full} of the {fail_all} that failed. It catches altered quotes, which is useful, but \
it's not a measure of quality.

**Test looks better than dev, and that isn't an improvement.** Dev holds the harder questions: all 9 that are close to the \
Phase 1C questions were kept there, along with 4 of the 6 vocabulary items. With 20 questions, the test numbers also move \
a lot on a single answer.

**Time** is about 30 to 60 seconds per question, nearly all of it the model writing. Search takes well under a second."""

COMMENT_B = """**Limit 4 gets the right chunk to the model more often, but the answers don't improve.** Recall@8 rises by 3 \
questions (`lookup-01`, `reference-02`, `single-21`). Key facts stay level, and complete answers fall from 9 to 7. Two answers \
clearly improve because the chunk now arrives: `single-21` gets the amounts right, and `lookup-01` reads article 2 correctly \
from inside the chunk labelled "Άρθρο 18". Others get worse although they had their chunk all along: `sector-03` loses two of \
its three overtime steps after one more chunk of the same decision joins the context. So the model reacts strongly to small \
changes in what it reads, and 32 questions can't separate the two settings.

**Decision: the final baseline keeps limit 2.** There is no evidence of better answers, and it's the setup Phase 1C was built \
with. The higher recall is real, so limit 4 is worth another try in Phase 3, behind a judge that can filter what the writer sees.

**The time difference isn't caused by the limit.** {same} questions got the very same answer in both runs, and those still took \
a median of {same_a:.0f} s in the first run and {same_b:.0f} s in the second. That's the load on the machine, so treat all times \
in this report as a rough guide."""

COMMENT_C = """**On its own, qwen3 looks better. Through hybrid search, almost none of that reaches the model.** Semantic search alone \
has the right chunk in its top 8 for 23 of 27 questions with qwen3, against 20 of 27 with bge-m3. It gains 4 (`sector-02`, \
`single-10`, `single-29`, `vocab-03`) and loses 1 (`reference-01`, which falls from rank 1 to rank 27 with the instruction and to \
rank 14 without it). But among the 8 chunks the model really gets, the count only goes from 13 to 14, and 10 of those 23 never \
arrive. This supports the main finding of this report: the limit is how the two lists are combined, and a better embedding model \
can't make up for that.

**The evidence is thin.** Four gains against one loss would happen by pure chance about one time in three. The small gain in hybrid \
search also hides more movement: with the instruction 3 questions come in and 2 drop out, without it 2 come in and 1 drops out. No \
answers were written with qwen3, so we don't know whether answers would get better.

**The instruction makes no clear difference.** Semantic's top 8 is the same size with and without it (23 of 27), and so is hybrid's \
(14 of 27), though not with the same questions. The top 50 differs by one question in its favour, and semantic's MRR by 0.02 against it.

**The cost is high once and low after that.** Embedding all the chunks takes about 2.5 hours on this laptop instead of 5 minutes, \
about 30 times slower, and the chunks added in Phase 5 would need the same treatment. A search takes about 0.15 s instead of 0.05 s, \
which nobody would notice next to the time the model takes to write.

**Decision: the final baseline stays on bge-m3.** That's what the test run used, and this experiment gives no reason to redo it. The \
qwen3 vectors stay in their own table, so this comparison can be repeated in seconds once the fusion is fixed in Phase 3. If \
semantic's lead holds up there, switching models becomes a real choice, and that one is for the project owner to make."""

TEST_COMMENT = """I didn't read the test answers, and nothing changed after this run: not the prompt, not the matching, not the \
key facts. The problem counts come from the code, without my reading. Don't compare single categories here: most have only 1 to 3 \
questions. The times are the weakest numbers: the run began with the qwen3 model still in memory, so Phase 4 should measure time \
again, with both systems under the same conditions."""

NEXT = """In the order I'd try them, cheapest and best-measured first:

1. **Fix the fusion.** Try a lower weight for keyword search, or semantic first with keyword only as a tie-breaker. A retrieval-only \
run takes seconds, so this can be tested before anything else.
2. **Rewriter.** Vocabulary mismatches are the clearest search failure. The rewriter's job is to add the law's words: \
\"γκαρσόνι\" to \"περιποιητής\", \"ένσημα\" to \"ημέρες εργασίας\", \"οικοδομές\" to \"εργοτάξια\".
3. **Judge.** For reading problems the model needs to ask whether a chunk applies to this person and this case, and to refuse if \
none does. `sector-01` and `reference-01` both show what it has to catch. This is where limit 4 can be tried again.
4. **A stronger writer.** Some failures remain even with the right chunk and nothing confusing around it, and answers change \
with small changes in context. Phase 4 can show how much of this belongs to this size of model. Today's numbers can't.
5. **Fetch the missing laws.** No search or judge can answer from Ν. 435/1976 while it isn't in the data. The list is in \
[missing-laws.md](missing-laws.md), and {in_other} of those laws are already in other volumes of this dataset."""

# id -> (label, title, explanation, quote from the baseline answer, or from the run named by the fifth value)
FAILURES = [
    ("vocab-06", "search problem", "The right chunk was first in one list and still never reached the model",
     "Semantic search ranked the right chunk first. Keyword search didn't find it at all, because the decision says "
     "«περιποιητάς (σερβιτόρους)» and never \"γκαρσόνι\". Hybrid search rewards chunks that both lists found, so this "
     "one fell to rank {rank}, and only the first few reach the model. The model didn't have the answer and said so. "
     "That was honest, but it counts as a wrong refusal, because the answer is in our data. {buried} This is the "
     "biggest single search finding: fusion, as built, punishes exactly the vocabulary mismatches that semantic search "
     "handles well.",
     "Δεν βρέθηκε απάντηση στα διαθέσιμα κείμενα για τα γκαρσόνι σε ταβέρνα"),
    ("vocab-01", "search problem", "A confident answer from a decree that excludes the case, and the check passed",
     "The right document, Π.Δ. 305/1996, says \"εργοτάξια\" where the question says \"οικοδομές\". It didn't make the top "
     "50. The model answered from Π.Δ. 16/1996 instead, whose own article 1 excludes «προσωρινά η κινητά εργοτάξια». "
     "Its quote really is in that chunk, so the citation check passed. The check proves that the words exist, not that "
     "the law applies. Finding the right document wouldn't be enough either: our copy is only its 32-word title, so the "
     "best possible answer names the decree and says its rules are missing. It's on the fetch list in "
     "[missing-laws.md](missing-laws.md).",
     "Τα κτίρια που στεγάζουν χώρους εργασίας πρέπει να έχουν δομή"),
    ("single-21", "search problem", "Our own limit threw away the answer, and the model filled the gap with a made-up number",
     "Search did its job: the right chunk was rank {rank}. But two chunks from the same decision ranked above it, and "
     "the limit of 2 per document removed it. The model saw only the sentence on the ceiling, so it gave one salary "
     "where the rule says half. Worse, it invented a minimum wage for 2024 in euros, from sources that stop in 1999, "
     "and nothing in the citation check can catch that, because it isn't a quote. With the limit at 4 the chunk arrives "
     "and the same model gives the right amounts.",
     "το κατώτατο μηνιαίο μισθό του 2024"),
    ("sector-01", "reading problem", "The right chunk came first, and the model read the wrong line",
     "The model avoided the trap: it used the decree for workers, not the 4 months that Ν. 2112/1920 gives employees. "
     "But the article is a ladder of periods (5, 8, 15, 30 and 60 days), and for six years' service it picked the line "
     "for two years: 15 days instead of 30. It also said the decree had been repealed, misreading a note that concerns "
     "only two other clauses. Its altered quote was 90% similar to the text and the check caught it. Better search "
     "can't help here.",
     "η καταγγελία γίνεται 15 ημέρας προ της λύσεως της συμβάσεως"),
    ("reference-01", "reading problem", "A question our data can't answer got a confident wrong answer",
     "The general overtime rate is in Ν. 435/1976, which isn't in our data, so the right answer is \"Δεν βρέθηκε\" plus a "
     "pointer to that law. The model answered 25% instead. Its source, Κ.Υ.Α. 18160/1983, is about the 41st hour of work, "
     "for workers whose pay is set by ministerial decision; the model widened it to every hour of overtime. The chunks "
     "pointing to Ν. 435/1976 weren't among the eight either (the best was first in semantic search and rank {rank} "
     "after fusion). But search alone doesn't explain it: the prompt says to refuse when the chunks don't answer, and "
     "the model didn't.",
     "κάθε ώρα υπερωρίας αμειβόταν με **25% προσαύξηση**"),
]


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def find_run(name):
    """The newest finished run with this name. Returns {"summary": …, "items": {id: record}, "dir": name} or None."""
    runs = sorted(RESULTS.glob(f"*_{name}"))
    runs = [r for r in runs if (r / "summary.json").exists()]
    if not runs:
        return None
    return {"summary": json.loads((runs[-1] / "summary.json").read_text(encoding="utf-8")),
            "items": {r["id"]: r for r in load_jsonl(runs[-1] / "items.jsonl")}, "dir": runs[-1].name}


def percent(value):
    return "-" if value is None else f"{value:.0%}"


def share_of(value, total):
    """'9 of 26 (35%)' from a share and its total."""
    if value is None:
        return "-"
    return f"{round(value * total)} of {total} ({value:.0%})"


def measures(group):
    """The rows of the comparison tables: (label, value) for one group of questions."""
    gold, answerable = group["with_gold_chunks"], group.get("answerable", 0)
    rows = [("Questions", group["questions"]),
            ("Right chunk among the 8 (recall@8)", share_of(group["recall_at_8"], gold)),
            ("Right chunk in the top 50 (recall@50)", share_of(group["recall_at_50"], gold)),
            ("Mean reciprocal rank (MRR)", "-" if group["mrr"] is None else f"{group['mrr']:.2f}")]
    if "fact_share" in group:
        rows += [("Key facts found", percent(group["fact_share"])),
                 ("Answers with every key fact", share_of(group["all_facts"], answerable)),
                 ("A gold law cited", share_of(group["gold_law_cited"], answerable)),
                 ("Citation check passed", share_of(group["check_passed"], answerable)),
                 ("Correct refusals", f"{group['correct_refusals']} of {group['unanswerable']}"),
                 ("Wrong refusals", f"{group['wrong_refusals']} of {answerable}"),
                 ("Search problems", group["search_problems"]),
                 ("Reading problems", group["reading_problems"])]
    rows.append(("Median time per question", f"{group['seconds_median']:.0f} s" if group["seconds_median"] >= 1
                 else f"{group['seconds_median']:.2f} s"))
    return rows


def compare_table(columns):
    """A table with one column per (heading, group)."""
    rows = [measures(group) for _, group in columns]
    lines = ["| Measure | " + " | ".join(h for h, _ in columns) + " |", "|---|" + "---:|" * len(columns)]
    for i, (label, _) in enumerate(rows[0]):
        lines.append(f"| {label} | " + " | ".join(str(r[i][1]) for r in rows) + " |")
    return "\n".join(lines)


def category_table(run):
    """Per-category numbers of a run with answers."""
    lines = ["| Category | Questions | Recall@8 | Recall@50 | MRR | Key facts | Every fact | Gold law cited | Check passed | "
             "Correct refusals | Wrong refusals | Search / reading problems |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, (label, _, _) in CATEGORY_TEXT.items():
        g = run["summary"]["by_category"].get(name)
        if not g:
            continue
        mrr = "-" if g["mrr"] is None else f"{g['mrr']:.2f}"
        lines.append(f"| {label} | {g['questions']} | {percent(g['recall_at_8'])} | {percent(g['recall_at_50'])} | {mrr} | "
                     f"{percent(g['fact_share'])} | {percent(g['all_facts'])} | {percent(g['gold_law_cited'])} | "
                     f"{percent(g['check_passed'])} | {g['correct_refusals']} of {g['unanswerable']} | "
                     f"{g['wrong_refusals']} of {g['answerable']} | {g['search_problems']} / {g['reading_problems']} |")
    return "\n".join(lines)


def retrieval_table(runs):
    """Semantic search alone and hybrid search, for each embedding run: (heading, run)."""
    lines = ["| Measure | " + " | ".join(h for h, _ in runs) + " |", "|---|" + "---:|" * len(runs)]
    rows = [("Semantic alone: right chunk in its top 8", "semantic_recall_at_8"),
            ("Semantic alone: right chunk in its top 50", "semantic_recall_at_50"),
            ("Semantic alone: MRR", "semantic_mrr"),
            ("Hybrid: right chunk among the 8 given to the model", "recall_at_8"),
            ("Hybrid: right chunk in the top 50", "recall_at_50"),
            ("Hybrid: MRR", "mrr")]
    for label, key in rows:
        cells = []
        for _, run in runs:
            value = run["summary"]["overall"][key]
            cells.append(f"{value:.2f}" if "mrr" in key else percent(value))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    seconds = [run["summary"]["overall"]["seconds_median"] for _, run in runs]
    lines.append("| Median search time per question | " + " | ".join(f"{s:.2f} s" for s in seconds) + " |")
    return "\n".join(lines)


def retrieval_by_category(runs, prefix=""):
    """Top 8 / top 50 / MRR per category, for hybrid search or, with prefix "semantic_", semantic search alone."""
    lines = ["| Category | Questions with a gold chunk | " + " | ".join(h for h, _ in runs) + " |",
             "|---|---:|" + "---:|" * len(runs)]
    for name, (label, _, _) in CATEGORY_TEXT.items():
        groups = [run["summary"]["by_category"].get(name) for _, run in runs]
        if not groups[0] or not groups[0]["with_gold_chunks"]:
            continue
        cells = [f"{percent(g[prefix + 'recall_at_8'])} / {percent(g[prefix + 'recall_at_50'])} / {g[prefix + 'mrr']:.2f}"
                 for g in groups]
        lines.append(f"| {label} | {groups[0]['with_gold_chunks']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def hand_check(run):
    """How often the automatic matching agrees with my reading of the same answers."""
    total, agree, disagreements = 0, 0, []
    for name, marks in HAND_FACTS.items():
        facts = run["items"][name]["score"]["facts"]
        if len(facts) != len(marks):
            raise SystemExit(f"HAND_FACTS[{name}] has {len(marks)} marks for {len(facts)} facts: redo it")
        for mark, fact in zip(marks, facts):
            total += 1
            same = (mark == "Y") == fact["present"]
            agree += same
            if not same:
                disagreements.append((name, fact["fact"], "found" if fact["present"] else "not found"))
    return total, agree, disagreements


def lost_after_semantic(run):
    """Questions whose gold chunk was in semantic search's top 8 but never reached the model: (pushed below rank 8 by
    fusion, removed as a repeat or by the limit per document although in the top 8 of hybrid search)."""
    lost = [r for r in run["items"].values() if r["retrieval"] and r["retrieval"]["semantic_rank"]
            and r["retrieval"]["semantic_rank"] <= 8 and not r["retrieval"]["in_context"]]
    pushed = [r for r in lost if not r["retrieval"]["rank"] or r["retrieval"]["rank"] > 8]
    return pushed, [r for r in lost if r not in pushed]


def check_against_facts(run):
    """(complete answers that passed, passed, complete answers that failed, failed) among the answerable questions."""
    answerable = [r for r in run["items"].values() if r["answerable"]]
    passed = [r for r in answerable if r["check"]["ok"]]
    failed = [r for r in answerable if not r["check"]["ok"]]
    complete = lambda rows: sum(r["score"]["fact_share"] == 1 for r in rows)    # noqa: E731
    return complete(passed), len(passed), complete(failed), len(failed)


def same_answer_times(a, b):
    """Median seconds in each run, over the questions that got the very same answer in both."""
    same = [k for k in a["items"] if a["items"][k]["answer"] == b["items"][k]["answer"]]
    seconds = lambda run: statistics.median(sum(run["items"][k]["times"].values()) for k in same)   # noqa: E731
    return len(same), seconds(a), seconds(b)


def write_failures(add, baseline, items):
    pushed, removed = lost_after_semantic(baseline)
    names = lambda rows: ", ".join(f"`{r['id']}`" for r in sorted(rows, key=lambda r: r["id"]))     # noqa: E731
    buried_text = (f"Fusion pushed the right chunk out of the top 8 like this for {len(pushed)} of the "
                   f"{baseline['summary']['overall']['with_gold_chunks']} dev questions with a gold chunk "
                   f"({names(pushed)}), although semantic search had it in its top 8. For {len(removed)} more "
                   f"({names(removed)}) it stayed in hybrid's top 8 but was removed as a repeat or by the limit.")
    for number, (name, label, title, why, quote) in enumerate(FAILURES, 1):
        record, item = baseline["items"][name], items[name]
        if quote not in record["answer"]:
            raise SystemExit(f"The quote for {name} is no longer in its answer: redo FAILURES")
        rank = record["retrieval"]["rank"] if record["retrieval"] else None
        ranks = record["retrieval"] or {}
        add(f"### {number}. `{name}`: {title}\n")
        add(f"**{label.capitalize()}.** {item['question']}\n")
        add(f"Expected: {'; '.join(item['key_facts'])}.\n")
        add(f"The model wrote: «{quote}…»\n")
        add(why.format(rank=rank, buried=buried_text) + "\n")
        place = ", ".join(f"{k} {ranks.get(key) or 'not found'}" for k, key in
                          (("hybrid rank", "rank"), ("semantic rank", "semantic_rank"), ("keyword rank", "keyword_rank")))
        add(f"Numbers: {place}; right chunk among the 8: {'yes' if ranks.get('in_context') else 'no'}; citation check: "
            f"{'passed' if record['check']['ok'] else 'failed'}.\n")


def main():
    baseline = find_run("oneshot-limit2-dev")
    limit4 = find_run("oneshot-limit4-dev")
    test = find_run("oneshot-limit2-test")
    retrieval_bge = find_run("retrieval-bge-m3-limit2-dev")
    retrieval_qwen = find_run("retrieval-qwen3-4b-limit2-dev")
    retrieval_plain = find_run("retrieval-qwen3-4b-plain-limit2-dev")
    missing = [n for n, r in (("baseline", baseline), ("limit 4", limit4), ("test", test), ("bge-m3", retrieval_bge),
                              ("qwen3", retrieval_qwen), ("qwen3 plain", retrieval_plain)) if not r]
    if missing:
        raise SystemExit(f"These runs are missing: {', '.join(missing)}")
    items = {i["id"]: i for i in load_jsonl(QUESTIONS)}
    total, agree, disagreements = hand_check(baseline)
    same, same_a, same_b = same_answer_times(baseline, limit4)
    stats_qwen = json.loads(STATS_QWEN.read_text(encoding="utf-8"))
    stats_bge = json.loads(STATS_BGE.read_text(encoding="utf-8"))

    lines = []

    def add(text=""):
        lines.append(text)

    add("# Evaluation report: measuring the one-shot baseline (Phase 2)\n")
    add("How good is the one-shot setup from Phase 1C, measured on a fixed set of questions with written-down answers? This "
        "file is generated by [`scripts/eval_report.py`](../scripts/eval_report.py) from the stored runs in "
        "[`eval/results/`](../eval/results/). Don't edit it by hand.\n")

    add("## At a glance\n")
    add(compare_table([("Dev (32 questions)", baseline["summary"]["overall"]),
                       ("Test (20 questions, run once)", test["summary"]["overall"])]) + "\n")
    dev, tst = baseline["summary"]["overall"], test["summary"]["overall"]
    pass_full, pass_all, fail_full, fail_all = check_against_facts(baseline)
    add(OVERALL.format(
        t_r8=round(tst["recall_at_8"] * tst["with_gold_chunks"]), t_gold=tst["with_gold_chunks"],
        t_full=round(tst["all_facts"] * tst["answerable"]), t_ans=tst["answerable"], t_cr=tst["correct_refusals"],
        t_un=tst["unanswerable"], t_wr=tst["wrong_refusals"],
        search=dev["search_problems"] + tst["search_problems"], reading=dev["reading_problems"] + tst["reading_problems"],
        d_r50=round(dev["recall_at_50"] * dev["with_gold_chunks"]), d_r8=round(dev["recall_at_8"] * dev["with_gold_chunks"]),
        d_gold=dev["with_gold_chunks"], d_s8=round(dev["semantic_recall_at_8"] * dev["with_gold_chunks"]),
        d_k50=round(dev["keyword_recall_at_50"] * dev["with_gold_chunks"]), pass_full=pass_full, pass_all=pass_all,
        fail_full=fail_full, fail_all=fail_all) + "\n")

    add("## What the test set contains\n")
    add(f"[`eval/questions.jsonl`](../eval/questions.jsonl) has {len(items)} questions in everyday modern Greek. Each has "
        "2 to 4 key facts a correct answer must contain, its gold sources (law, article, chunk) and notes on its traps. I "
        "wrote every item by reading the chunks, not from general knowledge. Where our data differs from today's law, the "
        "expected answer follows our data.\n")
    add("| Category | What it tests | Dev | Test | Example |")
    add("|---|---|---:|---:|---|")
    for name, (label, what, example) in CATEGORY_TEXT.items():
        dev = sum(i["category"] == name and i["split"] == "dev" for i in items.values())
        tst = sum(i["category"] == name and i["split"] == "test" for i in items.values())
        add(f"| {label} | {what} | {dev} | {tst} | {example} |")
    answerable = sum(i["answerable"] for i in items.values())
    add()
    add(f"{answerable} questions can be answered from our data and {len(items) - answerable} can't. Those {len(items) - answerable} "
        "are the 8 that must be refused and 2 of the follow-a-reference items, whose law is missing: for them the right "
        "answer says it wasn't found.\n")
    add("**Dev and test.** Dev is for looking at and improving. Test is for one final measurement, and the code refuses a "
        "second run. Questions close to the eight from Phase 1C, on which the prompt was revised, were kept in dev.\n")
    add("**Who checked it.** Code confirmed that every gold quote is in its chunk and that no question copies the law's "
        "wording. The project owner reviewed 20 items, the ones where my reading could most easily be wrong: 19 kept, 1 "
        "edited ([`eval/review.md`](../eval/review.md)). The other 32 had no second reader, so some expected answers may "
        "still be wrong.\n")

    add("## How it is measured\n")
    add("`.venv/bin/python -m labour_rag.evaluate --split dev` runs every question and saves the results in "
        "`eval/results/<date>_<config>/`, so runs can be compared.\n")
    add("| Measure | In plain words |")
    add("|---|---|")
    for label, text in (
            ("Recall@8", "Was a correct chunk among the 8 given to the model?"),
            ("Recall@50", "Was it in the top 50 of hybrid search? If yes but not in the 8, a better way of choosing could reach it."),
            ("MRR", "How high it ranked: 1.00 means always first, 0.50 always second, 0 outside the top 50."),
            ("Key facts", "The share of a question's key facts found in the answer, averaged over the answerable questions."),
            ("Every key fact", "Answers that contain all their facts. Closest to \"the answer is complete\"."),
            ("Gold law cited", "Did the answer cite a chunk from a law it should use?"),
            ("Citation check passed", "Every [n] exists and every quote is in its chunk. It says nothing about whether the reasoning is right."),
            ("Correct refusal", "A question our data can't answer got \"Δεν βρέθηκε…\"."),
            ("Wrong refusal", "A question our data can answer got \"Δεν βρέθηκε…\"."),
            ("Search problem", "The answer fell short and the right chunk wasn't among the 8."),
            ("Reading problem", "The answer fell short although the right chunk was among the 8, or the model answered a question it should have refused."),
    ):
        add(f"| {label} | {text} |")
    add()
    add(f"**How far to trust the key-fact score.** Matching needs no model. A fact counts as found if all its numbers are in "
        f"the answer and enough of its other words are: half if it has a number, {MIN_WORD_SHARE:.0%} if not. It ignores "
        f"accents and word endings, and it treats \"τρεις μήνες\", \"3 μήνες\" and \"τρίμηνο\" as the same. I read all 32 "
        f"baseline answers and marked all {total} facts of the answerable ones myself. The matching agrees on **{agree} of "
        f"{total}**. I tuned it once on these dev answers, before the test run, and didn't change it after. It still can't "
        "understand meaning: it can't see \"δεν\", and a number used in another sentence still counts. The disagreements "
        "that remain:\n")
    for name, fact, verdict in disagreements:
        add(f"- `{name}`: \"{fact}\", which the matching marked as {verdict}.")
    add()
    add("**Refusals** count only if the answer says \"Δεν βρέθηκε\" near its start, as the prompt asks. An answer that "
        "refuses in other words isn't counted: `lookup-01` wrote «δεν αναφέρεται στα αποσπάσματα». The check also doesn't ask "
        "whether a refusal names where the rule would be, which `reference-01` and `reference-03` expect. Neither was refused "
        "here, so no number changes, but it could matter in Phase 4.\n")
    add(f"**The sample is small.** On dev, one question moves recall by about 4 points and the share of complete answers by "
        f"about 4. Small differences below are noise.\n")

    add("## Experiments (a) and (b): the limit per document\n")
    add("Both use the same model and prompt. The only change is how many chunks one document may place among the 8.\n")
    add(compare_table([("(a) Limit 2, current", baseline["summary"]["overall"]),
                       ("(b) Limit 4", limit4["summary"]["overall"])]) + "\n")
    add("**(a) Limit 2, per category**\n")
    add(category_table(baseline) + "\n")
    add("**(b) Limit 4, per category**\n")
    add(category_table(limit4) + "\n")
    add(COMMENT_B.format(same=same, same_a=same_a, same_b=same_b) + "\n")

    add("## Experiment (c): bge-m3 or qwen3-embedding\n")
    add(f"Retrieval only, with no answers written, so it's fast to repeat. `qwen3-embedding:4b` got the same text as bge-m3, and "
        "its vectors are stored apart (`chunk_embeddings_qwen3_4b`), so the `chunks` table stayed untouched. Keyword search, "
        "fusion and the choice of 8 are the same. The model card recommends a short task instruction on the question side, so "
        "it was run both with and without one.\n")
    runs = [("bge-m3", retrieval_bge), ("qwen3 4b, with instruction", retrieval_qwen), ("qwen3 4b, no instruction", retrieval_plain)]
    add(retrieval_table(runs) + "\n")
    add("**Semantic search alone, per category** (in its top 8 / in its top 50 / MRR)\n")
    add(retrieval_by_category(runs, "semantic_") + "\n")
    add("**Hybrid search, per category** (among the 8 given to the model / in the top 50 / MRR)\n")
    add(retrieval_by_category(runs) + "\n")
    add("| Cost | bge-m3 | qwen3-embedding:4b |")
    add("|---|---:|---:|")
    add(f"| Model download | 1.2 GB | 2.5 GB |")
    add(f"| Numbers per vector | 1,024 | 2,560 |")
    # The stats cover the last stretch of a resumed run, so the whole job is worked out from its speed.
    qwen_hours = stats_qwen["chunks"] / stats_qwen["chunks_per_second"] / 3600
    add(f"| Embedding all {stats_bge['chunks']:,} chunks | {stats_bge['embedding_seconds'] / 60:.0f} min | "
        f"about {qwen_hours:.1f} hours |")
    add(f"| Speed | {stats_bge['chunks_per_second']:.1f} chunks/s | {stats_qwen['chunks_per_second']:.2f} chunks/s |")
    add()
    add(f"The speed for qwen3 was measured on the last {stats_qwen['embedded']:,} chunks. The first "
        f"{stats_qwen['chunks'] - stats_qwen['embedded']:,} ran before a pause, so the total is an estimate at that speed.\n")
    add(COMMENT_C + "\n")

    add("## Final baseline numbers on the test split\n")
    add("One run, with hybrid search, bge-m3 and limit 2. It came after experiments (a) and (b) but before (c) had finished; "
        "(c) gave no reason to change the setup. These are the numbers Phase 4 compares against.\n")
    add(category_table(test) + "\n")
    add(TEST_COMMENT + "\n")

    add("## The five most instructive failures\n")
    add("All five come from the dev baseline, so the test split stays unread. The question behind each label: was the answer "
        "in the chunks the model received? If not, it's a search problem. If yes, a reading problem.\n")
    write_failures(add, baseline, items)

    add("## What this means for Phase 3\n")
    in_other = re.search(r"(\d[\d,]*) of the missing laws are in another volume",
                         MISSING_LAWS.read_text(encoding="utf-8")).group(1)
    add(NEXT.format(in_other=in_other) + "\n")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
