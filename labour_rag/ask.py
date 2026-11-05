"""Answer a question from the labour-law chunks, one shot: search, pick 8 chunks without repeats, one
model call, then a citation check in code.

    .venv/bin/python -m labour_rag.ask "Πόσες ημέρες άδεια δικαιούται ο μισθωτός;" [--show-chunks] [--fusion rrf]

The instructions for the model are in prompts/answer.md, the fixed closing note in prompts/closing_note.md.
"""

import argparse
import textwrap
import time

from . import citations
from .config import ROOT
from .db import connect, friendly_errors
from .model_client import ModelClient
from .retrieve import CONTEXT_CHUNKS, MAX_PER_DOCUMENT, retrieve
from .search import DEFAULT_FUSION, FUSIONS

PROMPT_FILE = ROOT / "prompts/answer.md"
NOTE_FILE = ROOT / "prompts/closing_note.md"
NOTE_ADDED = "the model left out the closing note; it was added by the code"


def closing_note():
    return NOTE_FILE.read_text(encoding="utf-8").strip()


def system_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8").replace("{closing_note}", closing_note()).strip()


def source_label(chunk):
    """The heading the model sees for a chunk: citation, article, title and year."""
    parts = [chunk["citation"], chunk["article"]]
    if not chunk["citation_fallback"] and chunk["title"]:
        parts.append(chunk["title"])
    label = ", ".join(p for p in parts if p)
    if chunk["year"] and str(chunk["year"]) not in label:
        label += f" (έτος {chunk['year']})"
    if chunk["is_note"]:
        label += " [σημείωση του εκδότη]"
    return label


def user_message(question, chunks):
    sources = "\n\n".join(f"[{c['n']}] {source_label(c)}\n{c['text']}" for c in chunks)
    return f"Ερώτηση: {question}\n\nΑποσπάσματα:\n\n{sources}"


def ensure_closing_note(answer):
    """The answer with the closing note at the end; adds it if the model left it out. Returns (text, added)."""
    note = closing_note()
    if note in answer:
        return answer.strip(), False
    return f"{answer.strip()}\n\n{note}", True


def ask(conn, client, question, k=CONTEXT_CHUNKS, max_per_document=MAX_PER_DOCUMENT, fusion=DEFAULT_FUSION):
    """Everything about one answer: the chunks, what was removed, the answer, the check and the timings."""
    chunks, removed, times = retrieve(conn, client, question, k, max_per_document=max_per_document, fusion=fusion)
    messages = [{"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_message(question, chunks)}]

    started = time.perf_counter()
    raw = client.chat(messages)
    times["model answer"] = time.perf_counter() - started
    answer, note_added = ensure_closing_note(raw)

    started = time.perf_counter()
    check = citations.check(answer, chunks, closing_note())
    times["citation check"] = time.perf_counter() - started
    if note_added:
        check["warnings"].append(NOTE_ADDED)
    return {"question": question, "chunks": chunks, "removed": removed, "answer": answer, "raw_answer": raw,
            "check": check, "times": times, "model": client.chat_model, "tokens": dict(client.last_chat),
            "messages": messages}


def print_result(result, show_chunks=False):
    width = 100
    if show_chunks:
        print("=" * width + "\nWHAT THE MODEL RECEIVED (after the instructions in prompts/answer.md)\n" + "=" * width)
        print(result["messages"][1]["content"])
    print("=" * width + f"\n{result['question']}\n" + "=" * width)
    print(result["answer"])
    print("\nSOURCES")
    for c in result["chunks"]:
        print(f"  [{c['n']}] {c['id']}  {c['citation']}  {c['article'] or '-'}")
    if result["removed"]:
        dupes = sum(r["reason"] == "near-duplicate" for r in result["removed"])
        print(f"  (left out while choosing: {dupes} near-duplicate(s), "
              f"{len(result['removed']) - dupes} over the per-document limit)")
    check = result["check"]
    print("\nCITATION CHECK: " + ("OK" if check["ok"] else "FAILED"))
    print(f"  {len(check['citations'])} source(s) cited, {len(check['quotes'])} quote(s), "
          f"{sum(bool(q['found_in']) for q in check['quotes'])} found in the cited source"
          + ("; the answer is a refusal" if check["refusal"] else ""))
    for f in check["failures"]:
        print(textwrap.fill(f, width, initial_indent="  FAIL  ", subsequent_indent="        "))
    for w in check["warnings"]:
        print(textwrap.fill(w, width, initial_indent="  warn  ", subsequent_indent="        "))
    print("\nTIME")
    for step, seconds in result["times"].items():
        print(f"  {step:<16} {seconds:7.2f} s")
    print(f"  {'total':<16} {sum(result['times'].values()):7.2f} s   ({result['model']}, "
          f"{result['tokens'].get('prompt_tokens', 0)} prompt tokens, {result['tokens'].get('answer_tokens', 0)} "
          "answer tokens)")


def main():
    parser = argparse.ArgumentParser(description="Answer a question from the labour-law chunks, with sources.")
    parser.add_argument("question")
    parser.add_argument("--show-chunks", action="store_true", help="also print the chunks the model received")
    parser.add_argument("-k", type=int, default=CONTEXT_CHUNKS, help=f"chunks to give the model ({CONTEXT_CHUNKS})")
    parser.add_argument("--fusion", choices=FUSIONS, default=DEFAULT_FUSION,
                        help=f"how semantic and keyword search are combined ({DEFAULT_FUSION})")
    args = parser.parse_args()
    with connect() as conn:
        print_result(ask(conn, ModelClient.from_settings(), args.question, args.k, fusion=args.fusion), args.show_chunks)


if __name__ == "__main__":
    friendly_errors(main)
