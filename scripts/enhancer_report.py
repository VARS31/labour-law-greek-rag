"""Phase 3B: write docs/enhancer-report.md from the stored runs, after running what's missing.

    .venv/bin/python -I scripts/enhancer_report.py --run   # first run what's missing (database and Ollama, about 5 minutes)
    .venv/bin/python -I scripts/enhancer_report.py         # only rewrite the report from the stored runs

Retrieval only, on dev. The words around the numbers are hand-written (RESULT, EXAMPLES, MISSES, LIMITS and the text in main):
the script stops if the claims it can check stop holding, and all of them must be re-read whenever the runs change.
"""

import argparse
import itertools
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag import enhancer, evaluate  # noqa: E402
from labour_rag.db import friendly_errors  # noqa: E402
from labour_rag.retrieve import NEAR_IDENTICAL, overlap, word_set  # noqa: E402
from scripts.check_enhancer_prompt import MAX_SHARE, check  # noqa: E402
from scripts.eval_report import CATEGORY_TEXT, find_run  # noqa: E402

REPORT = ROOT / "docs/enhancer-report.md"
LIMIT = 2
VOCABULARY = ("vocab-01", "vocab-02", "vocab-03", "vocab-06")
PSEUDO_WORDS = {"single-01": "μισθώδεια", "single-21": "μεροκαιρομισθούντων", "single-26": "υπερπερισσότερον"}

RESULT = """**The enhancer doesn't bring more right chunks to the writer.** Without it, the right chunk arrives for {base} of {n} dev \
questions. The model's phrasings alone bring {var}. The phrasings together with the person's own question bring {withq}: the very \
same questions as without the enhancer. It costs a median of {seconds:.1f} s per question, so as a first step on every question it \
doesn't pay for itself.

**Why.** First, semantic search with qwen3 had already solved most of what the enhancer was for. Three of the 4 vocabulary questions \
arrive without it, at rank 1 or 2. In Phase 2, with bge-m3 and RRF, none did. Second, this model doesn't know the law's words. For \
`vocab-01` it writes "οικοδομικές εργασίες" every time and never "εργοτάξια", which is the word it would need. Its katharevousa is \
often not real Greek: {pseudo}.

**It isn't useless.** It reaches different chunks. Through the phrasings alone `sector-05` arrives, which plain search misses, and \
`sector-01` moves from rank 6 to 2. But others move down, and on these questions the two cancel out.

**What I'd do with it.** Not run it first. In the agent, search with the plain question first, and use the enhancer for the second \
try, when the judge says the chunks don't answer. Then the {seconds:.0f} seconds are spent only when they're needed, and the second \
try searches differently from the first. That is untested, because the judge doesn't exist yet."""

MISSES = """**The 5 questions that still miss, in every setup except where noted:**

- `single-09`: ranks 15th, or 19th with the question added. The phrasings don't find it at all.
- `sector-05`: stopped by the limit of 2 per document in plain search and with the question added. It arrives through the phrasings alone.
- `vocab-01`: moves from rank 19 to 12, not far enough. The right word never comes up.
- `reference-01`: stays near rank 27. It's the chunk bge-m3 ranked first, and qwen3 has never found it easily.
- `lookup-01`: a data problem. Article 2 sits inside the chunk labelled "Άρθρο 18", so asking for "άρθρο 2" can't find it, and keyword search ranks it 10th."""

# id, verdict, comment. Each comment's claims are checked in main.
EXAMPLES = [
    ("single-15", "Good", "Real words of the law: \"τοκετόν\" for \"γέννα\", and \"διάρκεια\" and \"κατανομή\" in proper form. The right chunk stays first."),
    ("lookup-03", "Good", "It finds the law in the question and adds none. The phrasings push the right chunk down to 9th, just outside the 8, and the 2 "
                          "places for keyword search bring it back. That's what `law_refs` is for."),
    ("sector-01", "Mixed", "Search improves: the right chunk moves from rank 6 to 2. But the rewrite turns \"εργάτης σε εργοστάσιο\" into \"μισθωτός σε "
                           "επιχείρηση\", the one detail that decides this sector trap, against rule 4 of the prompt. Nothing searches `rewritten` today, "
                           "but the writer should keep seeing the person's own words."),
    ("single-02", "Bad", "It names a law nobody asked about, Ν.Δ. 146/1979, in a search phrase, against rule 3 of the prompt. `law_refs` stays empty, so the "
                         "schema and the first check both pass. The code now drops any phrase with a number the question doesn't contain."),
    ("lookup-01", "Bad", "A placeholder is left in the text («[θέμα που αφορά ο νόμος]»), and article 2 becomes \"άρθρου β'\". `law_refs` is right, though."),
]

LIMITS = """- **No answers were written.** These numbers say which chunks reach the writer, not whether its answers are better.
- **Only 27 questions, and I've now read all of them.** One question is about 4 points. I wrote the examples and the checks after looking \
at these same questions, so a real test needs new ones. The test split wasn't touched.
- **One small model.** All of this is `ministral-3:8b`. A stronger model might know the law's words better. Phase 4 can test that.
- **Refusals weren't measured.** Questions that must be refused have no gold chunk, so they don't count in any number above.
- **The writer now sees old and new rules side by side.** On `single-15` it gets 14, 15 and 16 weeks. The filter is right to keep them, \
but picking the newest is now someone's job, and the judge is the place for it."""


def run_name(embedding="qwen3-4b", rule="units", mode=None):
    return evaluate.config_name({"retrieval_only": True, "embedding": embedding, "fusion": "semantic", "number_rule": rule,
                                 "enhancer": mode, "max_per_document": LIMIT, "split": "dev"})


def old_name(embedding):
    """Phase 3A's run of the same setup, with the old repeat filter."""
    return evaluate.config_name({"retrieval_only": True, "embedding": embedding, "fusion": "semantic", "max_per_document": LIMIT, "split": "dev"})


def _run(embedding="qwen3-4b", rule="units", mode=None, reuse=None):
    evaluate.run(argparse.Namespace(split="dev", system="one-shot", fusion="semantic", number_rule=rule, enhancer=mode, reuse_enhancer=reuse,
                                    max_per_document=LIMIT, embedding=embedding, retrieval_only=True, name=None, ids=None))


def run_missing():
    for embedding, rule in itertools.product(("qwen3-4b", "bge-m3"), ("units", "digits")):
        if not find_run(run_name(embedding, rule)):
            _run(embedding, rule)
    if not find_run(run_name(mode="variants")):
        _run(mode="variants")
    if not find_run(run_name(mode="with-question")):
        _run(mode="with-question", reuse=evaluate.RESULTS / find_run(run_name(mode="variants"))["dir"])


def arrived(run):
    return {i for i, r in run["items"].items() if r["retrieval"] and r["retrieval"]["in_context"]}


def count(group, key="recall_at_8"):
    return round(group[key] * group["with_gold_chunks"])


def names(ids):
    return ", ".join(f"`{i}`" for i in sorted(ids)) or "none"


def pairs_in(record, texts):
    """How many pairs of the delivered chunks share half of their words."""
    sets = [word_set(texts[c["id"]]) for c in record["chunks"]]
    return sum(overlap(a, b) >= NEAR_IDENTICAL for a, b in itertools.combinations(sets, 2))


def repeats_delivered(run, texts):
    """(pairs, questions) over a whole run."""
    found = [pairs_in(record, texts) for record in run["items"].values()]
    return sum(found), sum(n > 0 for n in found)


def chunk_label(chunk):
    citation = chunk["citation"] if len(chunk["citation"]) <= 40 else chunk["citation"][:40] + "…"
    return f"{citation}, {chunk['article']}" if chunk["article"] else citation


def filter_table(rows, texts):
    lines = ["| Repeat rule | Right chunk, qwen3 | Removed as repeats, qwen3 | Near-identical pairs reaching the writer, qwen3 | Right chunk, bge-m3 |",
             "|---|---:|---:|---:|---:|"]
    for label, qwen, bge in rows:
        removed = sum(r["removed"]["near_duplicate"] for r in qwen["items"].values())
        pairs, questions = repeats_delivered(qwen, texts)
        lines.append(f"| {label} | {count(qwen['summary']['overall'])} | {removed} | {pairs}, in {questions} questions | {count(bge['summary']['overall'])} |")
    return "\n".join(lines)


def changes_table(old, new):
    """The questions whose 8 chunks changed."""
    lines = ["| Question | Left the 8 | Joined the 8 |", "|---|---|---|"]
    changed = 0
    for item, record in new["items"].items():
        before, after = {c["id"]: c for c in old["items"][item]["chunks"]}, {c["id"]: c for c in record["chunks"]}
        if before.keys() != after.keys():
            changed += 1
            left = "; ".join(chunk_label(before[i]) for i in sorted(before.keys() - after.keys()))
            joined = "; ".join(chunk_label(after[i]) for i in sorted(after.keys() - before.keys()))
            lines.append(f"| `{item}` | {left} | {joined} |")
    return "\n".join(lines), changed


def numbers_table(columns):
    lines = ["| Measure | " + " | ".join(h for h, _ in columns) + " |", "|---|" + "---:|" * len(columns)]
    rows = [("Right chunk reaches the writer (recall@8)", lambda g: f"{count(g)} of {g['with_gold_chunks']}"),
            ("Right chunk in the top 50 (recall@50)", lambda g: f"{count(g, 'recall_at_50')} of {g['with_gold_chunks']}"),
            ("How high it ranks (MRR)", lambda g: f"{g['mrr']:.2f}"),
            ("Median time per question", lambda g: f"{g['seconds_median']:.1f} s")]
    for label, cell in rows:
        lines.append(f"| {label} | " + " | ".join(cell(run["summary"]["overall"]) for _, run in columns) + " |")
    return "\n".join(lines)


def category_table(columns):
    """Per category: recall@8 / recall@50 / MRR."""
    lines = ["| Category | Questions | " + " | ".join(h for h, _ in columns) + " |", "|---|---:|" + "---:|" * len(columns)]
    for category, (label, _, _) in CATEGORY_TEXT.items():
        groups = [run["summary"]["by_category"].get(category) for _, run in columns]
        if not groups[0] or not groups[0]["with_gold_chunks"]:
            continue
        cells = [f"{count(g)} / {count(g, 'recall_at_50')} / {g['mrr']:.2f}" for g in groups]
        lines.append(f"| {label} | {groups[0]['with_gold_chunks']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def arrival(run, item):
    retrieval = run["items"][item]["retrieval"]
    return f"{'**yes**' if retrieval['in_context'] else 'no'} (rank {retrieval['rank'] or 'over 50'})"


def output_block(add, record, base, var, withq):
    """One enhancer output, as the model gave it, and where the right chunk went."""
    output = record["enhancer"]
    add(f"> **Question:** {record['question']}")
    add(">")
    add(f"> **rewritten:** {output['rewritten']}")
    add(">")
    add("> **variants:** " + " / ".join(f"«{v}»" for v in output["variants"] + output["dropped_variants"]))
    add(">")
    add(f"> **law_refs:** {', '.join(output['law_refs']) or 'none'}. **topic_hint:** {output['topic_hint']}\n")
    if record["retrieval"]:
        item = record["id"]
        add(f"Does the right chunk arrive? Without the enhancer: {arrival(base, item)}. Phrasings alone: {arrival(var, item)}. "
            f"With the question added: {arrival(withq, item)}.\n")


def main():
    parser = argparse.ArgumentParser(description="Run the enhancer measurements and write the report.")
    parser.add_argument("--run", action="store_true", help="first run what has no stored run")
    args = parser.parse_args()
    if args.run:
        friendly_errors(run_missing)

    runs = {"base": find_run(run_name()), "digits": find_run(run_name(rule="digits")), "var": find_run(run_name(mode="variants")),
            "withq": find_run(run_name(mode="with-question")), "bge": find_run(run_name("bge-m3")), "bge_digits": find_run(run_name("bge-m3", "digits")),
            "old": find_run(old_name("qwen3-4b")), "old_bge": find_run(old_name("bge-m3"))}
    missing = [name for name, run in runs.items() if not run]
    if missing:
        raise SystemExit(f"These runs are missing, use --run: {', '.join(missing)}")
    base, var, withq = runs["base"], runs["var"], runs["withq"]
    n = base["summary"]["overall"]["with_gold_chunks"]
    texts = evaluate.chunk_texts()
    items = evaluate.load_questions()
    seconds = [r["enhancer"]["seconds"] for r in var["items"].values()]
    median_seconds = statistics.median(seconds)

    # The hand-written claims that code can check.
    claims = {"the counts behind RESULT": (count(base["summary"]["overall"]), count(var["summary"]["overall"]), count(withq["summary"]["overall"])) == (22, 21, 22),
              "with the question added, the same questions arrive": arrived(withq) == arrived(base),
              "phrasings alone: who moves": (arrived(var) - arrived(base), arrived(base) - arrived(var)) == ({"sector-05"}, {"single-14", "vocab-03"}),
              "3 of 4 vocabulary questions arrive at rank 1 or 2": sorted(base["items"][i]["retrieval"]["rank"] for i in VOCABULARY if i in arrived(base)) == [1, 2, 2],
              "vocab-01 never says the law's word": "εργοταξ" not in var["items"]["vocab-01"]["enhancer"]["raw"].lower().replace("ό", "ο").replace("ά", "α"),
              "sector-01 moves from 6 to 2": (base["items"]["sector-01"]["retrieval"]["rank"], var["items"]["sector-01"]["retrieval"]["rank"]) == (6, 2),
              "lookup-03: 9th without keyword search, and it arrives": (var["items"]["lookup-03"]["retrieval"]["semantic_rank"], var["items"]["lookup-03"]["retrieval"]["in_context"]) == (9, True),
              "single-02 invented a law": "146/1979" in var["items"]["single-02"]["enhancer"]["raw"] and not var["items"]["single-02"]["enhancer"]["law_refs"],
              "lookup-01 left a placeholder": "[θέμα" in var["items"]["lookup-01"]["enhancer"]["raw"],
              "the pseudo-words are there": all(w in var["items"][i]["enhancer"]["raw"] for i, w in PSEUDO_WORDS.items()),
              "the five misses": {i for i, r in base["items"].items() if r["retrieval"] and not r["retrieval"]["in_context"]} == {"single-09", "sector-05", "vocab-01", "reference-01", "lookup-01"},
              "the new filter changes no right chunk on qwen3": arrived(base) == arrived(runs["old"]),
              "the new filter brings back single-15 on bge-m3": arrived(runs["bge"]) - arrived(runs["old_bge"]) == {"single-15"} and not arrived(runs["old_bge"]) - arrived(runs["bge"]),
              "single-15 gets all three rules": {"glc-10348-002", "glc-06987-007", "glc-39164-004"} <= {c["id"] for c in base["items"]["single-15"]["chunks"]},
              "vocab-02 gets 6 chunks": len(base["items"]["vocab-02"]["chunks"]) == 6,
              "the literal rule's repeats on single-21 and vocab-02": (pairs_in(runs["digits"]["items"]["single-21"], texts), pairs_in(base["items"]["single-21"], texts),
                                                                       pairs_in(runs["digits"]["items"]["vocab-02"], texts), pairs_in(base["items"]["vocab-02"], texts)) == (9, 0, 6, 0),
              "single-32 keeps the newer act": "glc-39164-006" in {c["id"] for c in base["items"]["single-32"]["chunks"]} and "glc-21033-007" not in {c["id"] for c in base["items"]["single-32"]["chunks"]}}
    broken = [claim for claim, holds in claims.items() if not holds]
    if broken:
        raise SystemExit("These claims in the report no longer hold, redo its text:\n- " + "\n- ".join(broken))
    problems, example_rows = check(enhancer.PROMPT_FILE.read_text(encoding="utf-8"), items)
    if problems:
        raise SystemExit("The prompt's examples overlap the test set:\n- " + "\n- ".join(problems))

    lines = []

    def add(text=""):
        lines.append(text)

    add("# Enhancer report: rewriting the question before searching (Phase 3B)\n")
    add("Phase 3B adds the Query Enhancer: one model call that turns a person's question into searches in the words of the law. Retrieval "
        "only, on the dev questions, so no answers were written. It also makes qwen3 the default and fixes the repeat filter, because both "
        "change what the enhancer is measured against. This file is generated by [`scripts/enhancer_report.py`](../scripts/enhancer_report.py) "
        "from the stored runs in [`eval/results/`](../eval/results/). Don't edit it by hand.\n")

    add("## The result\n")
    pseudo = ", ".join(f"\"{w}\"" for w in PSEUDO_WORDS.values())
    add(RESULT.format(base=count(base["summary"]["overall"]), n=n, var=count(var["summary"]["overall"]), withq=count(withq["summary"]["overall"]),
                      seconds=median_seconds, pseudo=pseudo) + "\n")

    add("## The numbers\n")
    add("All three use qwen3, semantic search, the new repeat filter and limit 2. The first column is Phase 3A's default: it also reached "
        f"{count(runs['old']['summary']['overall'])} of {n} with the old filter.\n")
    columns = [("Without the enhancer", base), ("Phrasings alone", var), ("Phrasings + the question", withq)]
    add(numbers_table(columns) + "\n")
    add("**Per category.** Each cell shows recall@8 / recall@50 / MRR, with recall as a number of questions.\n")
    add(category_table(columns) + "\n")
    better = {name: [i for i, r in run["items"].items() if r["retrieval"] and (r["retrieval"]["rank"] or 99) < (base["items"][i]["retrieval"]["rank"] or 99)] for name, run in (("var", var), ("withq", withq))}
    worse = {name: [i for i, r in run["items"].items() if r["retrieval"] and (r["retrieval"]["rank"] or 99) > (base["items"][i]["retrieval"]["rank"] or 99)] for name, run in (("var", var), ("withq", withq))}
    add(f"**What moved.** Phrasings alone: {names(arrived(var) - arrived(base))} now arrives, {names(arrived(base) - arrived(var))} no longer do. "
        f"Compared with plain search, the right chunk ranks higher for {len(better['var'])} questions and lower for {len(worse['var'])}. With the question "
        f"added, it ranks higher for {len(better['withq'])} ({names(better['withq'])}) and lower for {len(worse['withq'])} ({names(worse['withq'])}).\n")
    add(f"**Time.** The enhancer takes a median of {median_seconds:.1f} s per question, from {min(seconds):.1f} to {max(seconds):.1f} s. Searching takes "
        "well under a second. Writing an answer takes about 30 to 60 s, so the enhancer would add roughly a fifth.\n")
    add(MISSES + "\n")

    add("## The vocabulary questions\n")
    add("These are the 4 on dev. The 2 on test weren't run.\n")
    for item in VOCABULARY:
        add(f"### `{item}`\n")
        output_block(add, var["items"][item], base, var, withq)

    add("## Five example outputs\n")
    add("Good and bad, from the dev questions.\n")
    for item, verdict, comment in EXAMPLES:
        add(f"### `{item}`: {verdict.lower()}\n")
        output_block(add, var["items"][item], base, var, withq)
        add(comment + "\n")

    add("## How the enhancer works\n")
    add("One call to `ministral-3:8b` at temperature 0, with its instructions in [`prompts/enhancer.md`](../prompts/enhancer.md). It returns JSON with "
        "`rewritten`, `variants`, `law_refs` and `topic_hint`. Asked again with 5 of the questions, it gave the same answer word for word.\n")
    outputs = [r["enhancer"] for r in var["items"].values()]
    named = [i for i, r in var["items"].items() if r["enhancer"]["law_refs"]]
    add(f"**The code checks the answer,** because a JSON schema fixes only its shape. All {sum(o['ok'] for o in outputs)} of {len(outputs)} answers could be read. "
        f"A law or article in `law_refs` must be written in the question: {sum(len(o['dropped_refs']) for o in outputs)} were dropped, and it found the law in all "
        f"{len(named)} questions that name one ({names(named)}). A search phrase with a number the question doesn't contain is dropped too: "
        f"{sum(len(o['dropped_variants']) for o in outputs)} phrases, in {sum(bool(o['dropped_variants']) for o in outputs)} questions. I added that check after seeing the results.\n")
    add("**Combining the searches.** Each chunk keeps its highest similarity to any one search, and chunks are ranked by that, so being found by several searches "
        "earns nothing. That reward is what buried the right chunks under RRF. Then come repeat removal and the limit, keeping 8. If `law_refs` isn't empty, "
        "keyword search for those laws may add up to 2 chunks after the first 6, like variant (e) in Phase 3A.\n")
    add("**Two ways of searching.** The brief was to search each phrasing, so that's measured. I also measured the phrasings together with the person's own question, "
        "because the phrasings can drift away from what plain search already finds, and they do: top 50 falls from "
        f"{count(base['summary']['overall'], 'recall_at_50')} to {count(var['summary']['overall'], 'recall_at_50')} without it. `enhancer.ranked` takes the question "
        "as an option, and the agent should pass it.\n")
    add(f"**The prompt's examples are on other topics.** [`scripts/check_enhancer_prompt.py`](../scripts/check_enhancer_prompt.py) checks them against all {len(items)} "
        "items of `eval/questions.jsonl`, and `tests/test_enhancer.py` runs the same check. A topic word or law number may appear nowhere in a question, key fact, gold "
        f"quote or note, and an example question may share at most {MAX_SHARE:.0%} of its words with a test question. **Result: no problems.**\n")
    add("| Example question | Topic | Topic words in the test set | Closest test question |")
    add("|---|---|---:|---|")
    for row in example_rows:
        add(f"| {row['question']} | {row['topic']} | 0 | `{row['closest']}`, {row['closest_share']:.0%} of its words |")
    add()
    add("The words they do share are common ones in any question about work, such as \"εργοδότης\" or \"πρέπει\".\n")

    add("## Housekeeping\n")
    add("### qwen3 is the default\n")
    add("Search, `labour_rag.ask` and `labour_rag.evaluate` now use `qwen3-embedding:4b` with its query instruction, on the project owner's decision after Phase 3A. "
        "`--embedding bge-m3` selects the old model, and its vectors stay in the `chunks` table. The scripts behind the Phase 1B and 1C reports stay on bge-m3, so "
        "those reports still describe what they measured. A new setup now also needs the model and about 2.5 hours of embedding.\n")
    add("### The repeat filter\n")
    add("Two chunks with different numbers are no longer repeats, and among real repeats the newest act is kept. So on bge-m3 the writer now gets Π.Δ. 176/1997's 16 "
        "weeks instead of losing it to a 15-week decision from 1989, and on qwen3 `single-32` gets the 1986 decision where it used to get the 1985 one with the same text.\n")
    add("**One choice the project owner should check: which numbers count.** The brief says different numbers in the text. I count numbers with a unit (`16 εβδομάδες`, `10%`, `27.012 δρχ`, `πέντε ημέρες`), not every digit. Read "
        "literally, the rule almost switches the filter off, because many digits in a chunk only name something: `Αριθ. 103100/4990 της 10/12 Δεκ. 1970 (ΦΕΚ Β΄897)`. The same "
        "bonus decision re-issued the next year differs in all of those. `--number-rule digits` selects the literal reading, and both are measured here:\n")
    add(filter_table([("Old filter", runs["old"], runs["old_bge"]), ("Numbers with a unit (new default)", base, runs["bge"]),
                      ("Every digit (literal)", runs["digits"], runs["bge_digits"])], texts) + "\n")
    add("The old filter was removing real differences: of the 26 pairs it treated as repeats on these questions, 23 differ in some digit and 14 in a number with a "
        "unit (counted once on both models, with no limit applied, and not stored). The new default keeps those 14 apart. Its removed count is higher only because the walk "
        "now reads all 30 results to find newer repeats.\n")
    add("Both new rules bring back the same question, so the literal reading buys nothing here, and it costs a lot. On `single-21` it hands the writer 9 near-identical pairs, and on "
        "`vocab-02` 6, all stating the same numbers with units: bonus decisions from different years repeating one rule. The new default hands over none on either. The "
        "8 pairs it does let through are chunks that really do state different numbers, which is what the rule wants. On `vocab-02` it delivers only 6 chunks, because "
        "repeats and the limit use up the first 30 results.\n")
    table, changed = changes_table(runs["old"], base)
    add(f"**Which dev questions change.** On qwen3, the 8 chunks change for {changed} questions, and the right chunk arrives for the same ones as before:\n")
    add(table + "\n")
    add(f"On bge-m3, `single-15` is the only question whose right chunk changes: it now arrives ({count(runs['old_bge']['summary']['overall'])} to "
        f"{count(runs['bge']['summary']['overall'])} of {n}). The fix has a side effect: `single-15` on qwen3 now hands the writer 14, 15 and 16 weeks at once.\n")

    add("## What this doesn't show\n")
    add(LIMITS + "\n")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
