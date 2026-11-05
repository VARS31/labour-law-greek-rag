"""Choose the chunks to give the model: search, then repeats and same-document repeats removed.

Near-identical chunks (the same ILO clause in ten conventions, a bonus decision re-issued every year) would
otherwise fill the model's context with one text, as Phase 1B showed (docs/search-report.md). Two chunks only count
as repeats if they state the same numbers, and among real repeats the newest act is the one kept.
"""

import re
import time

from . import search
from .embeddings import DEFAULT_EMBEDDING, embed_question
from .key_facts import _NUMBER_WORDS
from .normalize import fold, normalize

NEAR_IDENTICAL = 0.5    # two texts are near-identical when half of their distinct words are shared
# What a number measures, on folded text. Enough for the rules in our chunks. A number with a unit not listed here is
# ignored, so those chunks can still count as repeats, as all of them could before Phase 3B.
_UNITS = {"%": "%", "τοις εκατο": "%", "ημερομισθι": "ημερομίσθιο", "ημερ": "ημέρα", "ωρ": "ώρα", "εβδομαδ": "εβδομάδα",
          "μην": "μήνας", "ετ": "έτος", "χρον": "έτος", "λεπτ": "λεπτό", "δρχ": "δραχμή", "δραχμ": "δραχμή", "ευρω": "ευρώ",
          "ατομ": "άτομο", "μισθωτ": "άτομο"}
_AMOUNT = r"\d+(?:[.,]\d+)*"
_NUMBER = _AMOUNT + "|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_UNIT_WORD = (r"%|τοις\s+εκατο|ημερομισθι\w*|ημερ\w*|ωρ(?:α|ας|ες|ων)\b|εβδομαδ\w*|μην(?:α|ας|ες|ων|ος)\b|ετ(?:η|ων|ους|ος)\b"
              r"|χρον(?:ια|ων|ος|ου)\b|λεπτ(?:α|ων)\b|δρχ|δραχμ\w*|ευρω\b|ατομ\w*|μισθωτ\w*")
_NUMBER_THEN_UNIT = re.compile(rf"(?<![\w/.,])({_NUMBER})\s*({_UNIT_WORD})")
_MONEY_THEN_AMOUNT = re.compile(rf"(?:δρχ|δραχμ)\w*\.?\s*({_AMOUNT})")
CONTEXT_CHUNKS = 8      # chunks given to the model
MAX_PER_DOCUMENT = 2    # at most this many chunks from one document
POOL = 30               # ranked search results looked at to find those 8


def word_set(text):
    """Distinct words of a text, normalised, without numbers and words of 1-2 letters."""
    return {w for w in re.sub(r"[\d\W_]+", " ", fold(normalize(text))).split() if len(w) > 2}


def overlap(a, b):
    """Share of distinct words two word sets have in common (Jaccard)."""
    return len(a & b) / max(1, len(a | b))


def rule_numbers(text):
    """What a chunk's numbers measure: {("15", "εβδομάδα"), ("10", "%"), ("27012", "δραχμή")}. Numbers that only name
    something (article 8, Αριθ. 103100/4990, ΦΕΚ Β΄897, a date) are left out: the same decision re-issued every year
    differs in those and is still a repeat. Digits and number words count the same: "πέντε ημέρες" = "5 ημέρες"."""
    folded = fold(normalize(text))
    found = set()
    for number, unit_word in _NUMBER_THEN_UNIT.findall(folded):
        value = str(_NUMBER_WORDS.get(number, re.sub(r"[.,]", "", number)))
        found.add((value, next(name for start, name in _UNITS.items() if unit_word.startswith(start))))
    found.update((re.sub(r"[.,]", "", amount), "δραχμή") for amount in _MONEY_THEN_AMOUNT.findall(folded))
    return found


def all_digits(text):
    """Every number written in digits, for the literal reading of the rule. Almost switches the filter off: see
    docs/enhancer-report.md."""
    return set(re.findall(r"\d+", normalize(text)))


NUMBER_RULES = {"units": rule_numbers, "digits": all_digits}
NUMBER_RULE = "units"


def _newer(chunk, than):
    return chunk["year"] is not None and than["year"] is not None and chunk["year"] > than["year"]


def select(results, k=CONTEXT_CHUNKS, max_per_document=MAX_PER_DOCUMENT, number_rule=NUMBER_RULE):
    """Walk the ranked results and keep the first k that are not a repeat of a kept chunk and whose document doesn't
    have max_per_document chunks yet. A repeat has half of its words in common with a kept chunk and states the same
    numbers. If a repeat comes from a newer act, it takes the older one's place, so the walk looks at all the results
    even when k are kept. Returns (kept, removed); each removed result says why."""
    numbers_of = NUMBER_RULES[number_rule]
    kept, removed, per_doc = [], [], {}
    for r in results:
        words, numbers = word_set(r["text"]), numbers_of(r["text"])
        twin = next((i for i, (_, cw, cn) in enumerate(kept) if cn == numbers and overlap(words, cw) >= NEAR_IDENTICAL), None)
        if twin is not None:
            older = kept[twin][0]
            if _newer(r, older) and (r["doc_id"] == older["doc_id"] or per_doc.get(r["doc_id"], 0) < max_per_document):
                kept[twin] = (r, words, numbers)
                per_doc[older["doc_id"]] -= 1
                per_doc[r["doc_id"]] = per_doc.get(r["doc_id"], 0) + 1
                removed.append({**older, "reason": "near-duplicate", "of": r["id"]})
            else:
                removed.append({**r, "reason": "near-duplicate", "of": older["id"]})
        elif len(kept) == k:
            continue
        elif per_doc.get(r["doc_id"], 0) >= max_per_document:
            removed.append({**r, "reason": "same document", "of": None})
        else:
            kept.append((r, words, numbers))
            per_doc[r["doc_id"]] = per_doc.get(r["doc_id"], 0) + 1
    return [dict(r, n=i) for i, (r, _, _) in enumerate(kept, 1)], removed


def retrieve(conn, client, question, k=CONTEXT_CHUNKS, pool=POOL, max_per_document=MAX_PER_DOCUMENT,
             fusion=search.DEFAULT_FUSION, embedding=DEFAULT_EMBEDDING):
    """The k chunks for a question, numbered n = 1..k, plus what was removed and the time of each step."""
    times = {}
    started = time.perf_counter()
    vector = embed_question(client, question, embedding)
    times["embed question"] = time.perf_counter() - started

    started = time.perf_counter()
    results = search.ranked(conn, client, question, pool, fusion, vector=vector, embedding=embedding)
    times["search"] = time.perf_counter() - started

    started = time.perf_counter()
    kept, removed = select(results, k, max_per_document)
    times["remove repeats"] = time.perf_counter() - started
    return kept, removed, times
