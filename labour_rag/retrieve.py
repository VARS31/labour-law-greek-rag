"""Choose the chunks to give the model: search, then near-duplicates and same-document repeats removed.

Near-identical chunks (the same ILO clause in ten conventions, a bonus decision re-issued every year) would
otherwise fill the model's context with one text, as Phase 1B showed (docs/search-report.md).
"""

import re
import time

from . import search
from .normalize import fold, normalize

NEAR_IDENTICAL = 0.5    # two texts are near-identical when half of their distinct words are shared
CONTEXT_CHUNKS = 8      # chunks given to the model
MAX_PER_DOCUMENT = 2    # at most this many chunks from one document
POOL = 30               # ranked search results looked at to find those 8


def word_set(text):
    """Distinct words of a text, normalised, without numbers and words of 1-2 letters."""
    return {w for w in re.sub(r"[\d\W_]+", " ", fold(normalize(text))).split() if len(w) > 2}


def overlap(a, b):
    """Share of distinct words two word sets have in common (Jaccard)."""
    return len(a & b) / max(1, len(a | b))


def select(results, k=CONTEXT_CHUNKS, max_per_document=MAX_PER_DOCUMENT):
    """Walk the ranked results and keep the first k that are not a near-duplicate of a kept chunk and whose
    document doesn't have max_per_document chunks yet. Returns (kept, removed); each removed result says why."""
    kept, removed, per_doc = [], [], {}
    for r in results:
        if len(kept) == k:
            break
        words = word_set(r["text"])
        twin = next((c for c, cw in kept if overlap(words, cw) >= NEAR_IDENTICAL), None)
        if twin:
            removed.append({**r, "reason": "near-duplicate", "of": twin["id"]})
        elif per_doc.get(r["doc_id"], 0) >= max_per_document:
            removed.append({**r, "reason": "same document", "of": None})
        else:
            kept.append((r, words))
            per_doc[r["doc_id"]] = per_doc.get(r["doc_id"], 0) + 1
    return [dict(r, n=i) for i, (r, _) in enumerate(kept, 1)], removed


def retrieve(conn, client, question, k=CONTEXT_CHUNKS, pool=POOL, max_per_document=MAX_PER_DOCUMENT,
             fusion=search.DEFAULT_FUSION):
    """The k chunks for a question, numbered n = 1..k, plus what was removed and the time of each step."""
    times = {}
    started = time.perf_counter()
    vector = client.embed([normalize(question)])[0]
    times["embed question"] = time.perf_counter() - started

    started = time.perf_counter()
    results = search.ranked(conn, client, question, pool, fusion, vector=vector)
    times["search"] = time.perf_counter() - started

    started = time.perf_counter()
    kept, removed = select(results, k, max_per_document)
    times["remove repeats"] = time.perf_counter() - started
    return kept, removed, times
