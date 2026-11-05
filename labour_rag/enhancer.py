"""The Query Enhancer: one model call that turns a person's question into searches in the words of the law.

    .venv/bin/python -m labour_rag.enhancer "Πόσο δώρο παίρνω;" [--search]

The instructions are in prompts/enhancer.md. The answer is checked here, because a JSON schema fixes only its shape: a law
reference or a search phrase with a number that isn't written in the question is dropped, whatever the model says.
"""

import argparse
import json
import re
import time

from . import search
from .config import ROOT
from .db import connect, friendly_errors
from .embeddings import DEFAULT_EMBEDDING
from .law_mentions import find_mentions, label
from .model_client import ModelClient
from .normalize import normalize
from .retrieve import select

PROMPT_FILE = ROOT / "prompts/enhancer.md"
MAX_VARIANTS = 3
SCHEMA = {"type": "object",
          "properties": {"rewritten": {"type": "string"},
                         "variants": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": MAX_VARIANTS},
                         "law_refs": {"type": "array", "items": {"type": "string"}},
                         "topic_hint": {"type": "string"}},
          "required": ["rewritten", "variants", "law_refs", "topic_hint"]}
# What the search uses: the variants alone, or with the person's own question as well. See docs/enhancer-report.md.
MODES = {"variants": False, "with-question": True}


def system_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8").strip()


def unwritten_numbers(text, question):
    """The numbers in a text that the question doesn't contain. A law's year may be spelled out, so 1983 counts as written
    in a question that says "Ν. 1387/83"."""
    written = set(re.findall(r"\d+", normalize(question)))
    written |= {f"19{n}" for n in written if len(n) == 2}
    return [n for n in re.findall(r"\d+", normalize(text)) if n not in written]


def written_in_question(ref, question):
    """True if a law reference has numbers and all of them are written in the question."""
    return bool(re.search(r"\d", ref)) and not unwritten_numbers(ref, question)


def parse_output(raw, question):
    """The model's answer as a clean dict. If it can't be used, the question itself becomes the only search and ok is
    False, so a bad answer costs quality and never stops a search."""
    try:
        data = json.loads(raw)
        if not isinstance(data["variants"], list) or not isinstance(data["law_refs"], list):
            raise ValueError("not lists")
        rewritten = data["rewritten"].strip()
        variants = list(dict.fromkeys(v.strip() for v in data["variants"] if v.strip()))[:MAX_VARIANTS]
        refs = [r.strip() for r in data["law_refs"] if r.strip()]
        topic = data["topic_hint"].strip()
        if not rewritten or not variants:
            raise ValueError("empty answer")
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"rewritten": question, "variants": [question], "law_refs": [], "topic_hint": "", "dropped_refs": [],
                "dropped_variants": [], "ok": False}
    kept_refs = [r for r in refs if written_in_question(r, question)]
    kept_variants = [v for v in variants if not unwritten_numbers(v, question)]
    return {"rewritten": rewritten, "variants": kept_variants or [question], "law_refs": kept_refs, "topic_hint": topic,
            "dropped_refs": [r for r in refs if r not in kept_refs],
            "dropped_variants": [v for v in variants if v not in kept_variants], "ok": True}


def enhance(client, question):
    """One call to the chat model, at temperature 0. The cleaned answer, plus the seconds it took and the raw text."""
    started = time.perf_counter()
    raw = client.chat([{"role": "system", "content": system_prompt()}, {"role": "user", "content": f"Ερώτηση: {question}\nJSON:"}],
                      response_format=SCHEMA, temperature=0)
    return {**parse_output(raw, question), "seconds": round(time.perf_counter() - started, 2), "raw": raw,
            "tokens": dict(client.last_chat)}


def law_keywords(law_refs):
    """Words for keyword search, with a law in the form chunk headers use: "Ν. 1387/83" -> "Ν. 1387/1983"."""
    words = []
    for ref in law_refs:
        mentions = find_mentions(ref, any_year=True)
        words.append(" ".join(label(m.abbr, m.number, m.year) for m in mentions) if mentions else ref)
    return " ".join(words)


def ranked(conn, client, output, question=None, k=10, embedding=DEFAULT_EMBEDDING):
    """The ranked chunks for an enhancer's output: its variants, plus the person's question if given."""
    queries = output["variants"] + ([question] if question else [])
    return search.multi_query(conn, client, queries, law_keywords(output["law_refs"]), k, embedding=embedding)


def main():
    parser = argparse.ArgumentParser(description="Turn a question into searches in the words of the law.")
    parser.add_argument("question")
    parser.add_argument("--search", action="store_true", help="also search, and show the chunks that would reach the writer")
    args = parser.parse_args()
    client = ModelClient.from_settings()
    output = enhance(client, args.question)
    print(json.dumps({k: output[k] for k in ("rewritten", "variants", "law_refs", "topic_hint", "dropped_refs",
                                             "dropped_variants", "ok", "seconds")},
                     ensure_ascii=False, indent=1))
    if args.search:
        with connect() as conn:
            fused, _ = ranked(conn, client, output, args.question, k=30)
        for c in select(fused)[0]:
            print(f"[{c['n']}] {c['id']}  {c['citation']}  {c['article'] or '-'}")


if __name__ == "__main__":
    friendly_errors(main)
