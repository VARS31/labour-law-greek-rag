"""Check eval/questions.jsonl against the chunks, and write the review file.

Checks that every item has the agreed fields, that every gold chunk exists and contains its quote, whether the same
quote also appears in chunks not listed as gold, and whether a question copies the wording of its source.

Usage:
    .venv/bin/python -I scripts/check_eval_set.py                  # run the checks and print the counts
    .venv/bin/python -I scripts/check_eval_set.py --write-review   # also write eval/review.md (never overwrites it)
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag.normalize import fold, normalize  # noqa: E402

QUESTIONS = ROOT / "eval/questions.jsonl"
REVIEW = ROOT / "eval/review.md"
CHUNKS = ROOT / "data/processed/labour_chunks.jsonl"

FIELDS = ["id", "question", "answerable", "key_facts", "gold_sources", "category", "split", "notes"]
CATEGORIES = {"single_source": "answerable from one place", "sector_trap": "sector trap",
              "vocabulary": "vocabulary mismatch", "follow_reference": "follow a reference",
              "must_refuse": "must be refused", "exact_lookup": "exact law lookup"}
COPIED_WORDS = 5    # a question sharing this many consecutive words with its source is flagged

# The 20 items for the review, mixed across categories, leaning to those where my reading could most easily be wrong.
REVIEW_IDS = ["single-06", "single-12", "single-15", "single-17", "single-22", "single-25", "single-32",
              "sector-01", "sector-02", "sector-03", "sector-04",
              "vocab-01", "vocab-03", "vocab-04",
              "reference-01", "reference-02", "reference-03",
              "refuse-03", "refuse-05",
              "lookup-01"]


def plain(text):
    """Text reduced to lowercase words without accents, for comparing quotes with chunks."""
    return " ".join(re.sub(r"[^\w%/]+", " ", fold(normalize(text))).split())


def quote_in(quote, text):
    """Whether every part of a quote, split at "…", appears in the text in order."""
    position, target = 0, plain(text)
    for part in quote.split("…"):
        position = target.find(plain(part), position)
        if position < 0:
            return False
        position += len(plain(part))
    return True


def copied_run(question, text):
    """The longest run of consecutive question words that also appears in the text."""
    words, target = plain(question).split(), f" {plain(text)} "
    best = 0
    for start in range(len(words)):
        for end in range(start + best + 1, len(words) + 1):
            if f" {' '.join(words[start:end])} " not in target:
                break
            best = end - start
    return best


def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def check(items, chunks):
    """Returns (errors, warnings): errors make the set unusable, warnings are for a person to look at."""
    errors, warnings = [], []
    seen = set()
    for item in items:
        name = item.get("id", "?")
        missing = [f for f in FIELDS if f not in item]
        if missing:
            errors.append(f"{name}: missing fields {missing}")
            continue
        if name in seen:
            errors.append(f"{name}: duplicate id")
        seen.add(name)
        if item["category"] not in CATEGORIES:
            errors.append(f"{name}: unknown category {item['category']}")
        if item["split"] not in ("dev", "test"):
            errors.append(f"{name}: unknown split {item['split']}")
        if not 2 <= len(item["key_facts"]) <= 4:
            errors.append(f"{name}: {len(item['key_facts'])} key facts, expected 2 to 4")
        if item["answerable"] and not item["gold_sources"]:
            errors.append(f"{name}: answerable but has no gold source")

        gold = {c for s in item["gold_sources"] for c in s["chunk_ids"]}
        for source in item["gold_sources"]:
            for chunk_id in source["chunk_ids"]:
                if chunk_id not in chunks:
                    errors.append(f"{name}: chunk {chunk_id} doesn't exist")
                elif not quote_in(source["quote"], chunks[chunk_id]["text"]):
                    errors.append(f"{name}: quote not found in {chunk_id}: {source['quote'][:70]}")
            others = [c["id"] for c in chunks.values() if c["id"] not in gold and quote_in(source["quote"], c["text"])]
            if others:
                warnings.append(f"{name}: the same quote is also in {', '.join(others)}")
        for chunk_id in sorted(gold & chunks.keys()):
            run = copied_run(item["question"], chunks[chunk_id]["text"])
            if run >= COPIED_WORDS:
                warnings.append(f"{name}: question shares {run} consecutive words with {chunk_id}")
    return errors, warnings


def print_counts(items):
    table = collections.Counter((i["category"], i["split"]) for i in items)
    print(f"{'category':<20}{'dev':>5}{'test':>6}{'all':>6}")
    for category in CATEGORIES:
        dev, test = table[category, "dev"], table[category, "test"]
        print(f"{category:<20}{dev:>5}{test:>6}{dev + test:>6}")
    dev = sum(i["split"] == "dev" for i in items)
    print(f"{'total':<20}{dev:>5}{len(items) - dev:>6}{len(items):>6}")
    print(f"answerable: {sum(i['answerable'] for i in items)}, not answerable: "
          f"{sum(not i['answerable'] for i in items)}")


def review_text(items):
    by_id = {i["id"]: i for i in items}
    out = ["# Evaluation set: items for review", "",
           f"{len(REVIEW_IDS)} of the {len(items)} items in `eval/questions.jsonl`. I read the source passage for every item, "
           "and code has checked that each quote below appears in its chunk. "
           "I picked the items where my reading could most easily be wrong, so this sample is harder than the rest.",
           "", "For each item, replace the Verdict line with one word (keep, edit or reject) and add a note if you "
           "wish. Expected answers follow our data, even where today's law says something else.", ""]
    for name in REVIEW_IDS:
        item = by_id[name]
        answerable = "yes" if item["answerable"] else "no, the right answer says it wasn't found"
        out += [f"## {name} ({CATEGORIES[item['category']]}, {item['split']})", "",
                f"**Question:** {item['question']}", "", f"**Answerable from our data:** {answerable}", "",
                "**Expected key facts:**", ""]
        out += [f"- {fact}" for fact in item["key_facts"]]
        out += ["", "**Gold source:**", ""]
        if item["gold_sources"]:
            for source in item["gold_sources"]:
                out.append(f"- {source['law']}, {source['article']} ({', '.join(source['chunk_ids'])}): "
                           f"«{source['quote']}»")
        else:
            out.append("- None: the data has nothing on this.")
        out += ["", f"**Notes:** {item['notes']}", "", "Verdict: keep / edit / reject", ""]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Check the evaluation set against the chunks.")
    parser.add_argument("--write-review", action="store_true", help="also write eval/review.md (never overwrites it)")
    args = parser.parse_args()

    items = load_jsonl(QUESTIONS)
    chunks = {c["id"]: c for c in load_jsonl(CHUNKS)}
    errors, warnings = check(items, chunks)
    print_counts(items)
    for warning in warnings:
        print("warn ", warning)
    for error in errors:
        print("ERROR", error)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")

    if args.write_review and not errors:
        if REVIEW.exists():
            print(f"{REVIEW} already exists and may hold your verdicts; left as it is")
        else:
            REVIEW.write_text(review_text(items), encoding="utf-8")
            print(f"wrote {REVIEW}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
