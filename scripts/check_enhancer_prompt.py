"""Check that the examples in prompts/enhancer.md don't teach to the test: their topics must not be in eval/questions.jsonl.

    .venv/bin/python -I scripts/check_enhancer_prompt.py

For each example: its topic words and its law numbers must appear nowhere in the test set (questions, key facts, gold quotes,
notes), and its question must not share more than MAX_SHARE of its words with any test question. Words that are simply common
in labour law are listed, not failed. Exits with an error if a check fails. tests/test_enhancer.py runs the same check.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag.enhancer import PROMPT_FILE, SCHEMA, parse_output  # noqa: E402
from labour_rag.evaluate import load_questions  # noqa: E402
from labour_rag.key_facts import _word_found, parse  # noqa: E402

MAX_SHARE = 0.4     # of an example question's words that a test question may share with it
_EXAMPLE = re.compile(r"^Ερώτηση: (.+)\nJSON: (\{.*\})$", re.MULTILINE)


def examples(prompt):
    """[(question, the example's answer as a dict)] from the text of the prompt."""
    return [(question, json.loads(answer)) for question, answer in _EXAMPLE.findall(prompt)]


def words(text):
    return set(parse(text)[1])


def item_text(item):
    """Everything in a test item that could teach something."""
    quotes = [source["quote"] for source in item["gold_sources"] if source.get("quote")]
    laws = [source.get("law") or "" for source in item["gold_sources"]]
    return " ".join([item["question"], *item["key_facts"], *quotes, *laws, item.get("notes") or ""])


def check(prompt, items):
    """A list of problems, and one row of findings per example."""
    problems, rows = [], []
    texts = {item["id"]: item_text(item) for item in items}
    stems = {item_id: words(text) for item_id, text in texts.items()}
    question_stems = {item["id"]: words(item["question"]) for item in items}
    found = examples(prompt)
    if not found:
        problems.append("no examples found in the prompt")
    for question, answer in found:
        cleaned = parse_output(json.dumps(answer, ensure_ascii=False), question)
        if not cleaned["ok"] or cleaned["dropped_refs"] or set(answer) != set(SCHEMA["required"]):
            problems.append(f"the example breaks the prompt's own rules: {question}")

        topic_hits = {w: sorted(i for i, s in stems.items() if _word_found(w, s)) for w in words(answer["topic_hint"])}
        for word, ids in topic_hits.items():
            if ids:
                problems.append(f"topic word «{word}» of «{question}» is in the test set: {', '.join(ids)}")

        numbers = set(re.findall(r"\d{3,}", " ".join([question, *answer["law_refs"], *answer["variants"]])))
        for number in numbers:
            ids = sorted(i for i, t in texts.items() if re.search(rf"(?<!\d){number}(?!\d)", t))
            if ids:
                problems.append(f"law number {number} of «{question}» is in the test set: {', '.join(ids)}")

        own = words(question)
        shares = {i: len({w for w in own if _word_found(w, s)}) / max(1, len(own)) for i, s in question_stems.items()}
        closest = max(shares, key=shares.get)
        if shares[closest] > MAX_SHARE:
            problems.append(f"«{question}» shares {shares[closest]:.0%} of its words with {closest}")

        all_own = words(" ".join([question, answer["rewritten"], *answer["variants"]]))
        rows.append({"question": question, "topic": answer["topic_hint"], "topic_words": sorted(topic_hits),
                     "closest": closest, "closest_share": shares[closest],
                     "shared_with_questions": sorted(w for w in all_own if any(_word_found(w, s) for s in question_stems.values()))})
    return problems, rows


def main():
    items = load_questions()
    problems, rows = check(PROMPT_FILE.read_text(encoding="utf-8"), items)
    print(f"{len(rows)} examples checked against {len(items)} test items")
    for row in rows:
        print(f"- {row['question']}\n  topic words {row['topic_words']}: in no test item\n  closest test question {row['closest']}, "
              f"{row['closest_share']:.0%} of its words\n  common words shared with test questions: {', '.join(row['shared_with_questions']) or 'none'}")
    if problems:
        raise SystemExit("PROBLEMS:\n" + "\n".join(problems))
    print("OK: no example topic is in the test set")


if __name__ == "__main__":
    main()
