"""Check a model answer against the chunks it was given.

Failures (the answer can't be trusted as written):
  - a citation [n] that doesn't refer to a provided chunk
  - a quote with no citation next to it
  - a quote whose words don't appear in the cited chunk (accents, case and punctuation ignored; "…" inside a
    quote may skip words, but the pieces must appear in that order)
  - an answer that is not a refusal but cites nothing
Warnings (worth a look): sentences without a citation, no year named, the closing note missing.
"""

import difflib
import re

from .normalize import fold, normalize

CITATION = re.compile(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]")                    # [1]  [1, 3]  [2-4]
QUOTE = re.compile(r"«([^«»]{4,}?)»|“([^“”]{4,}?)”|\"([^\"]{4,}?)\"")
ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.|\[\s*…\s*\]|\(\s*…\s*\))\s*")
REFUSAL = re.compile(r"Δεν\s+βρέθηκε", re.IGNORECASE)                       # the words the prompt asks for
REFUSAL_REACH = 300     # a refusal is said at the start; later it's about one detail of an answer
_SOURCES = r"(?:αποσπασματα|κειμενα|πηγες|παραθεματα)"
# In other words, on folded text: "το άρθρο 2 δεν αναφέρεται στα αποσπάσματα", "τα αποσπάσματα δεν αναφέρουν τίποτα"
_REFUSAL_IN_OTHER_WORDS = re.compile(
    r"\bδεν\s+(?:\w+\s+)?(?:αναφερ|περιεχ|περιλαμβαν|υπαρχ|βρισκ|εμφανιζ|προκυπτ|γινεται\s+αναφορα)\w*\s+"
    rf"(?:\w+\s+){{0,3}}?στ(?:α|ις)\s+(?:\w+\s+)?{_SOURCES}"
    rf"|\b{_SOURCES}\s+(?:\w+\s+){{0,2}}?δεν\s+(?:αναφερ|περιεχ|περιλαμβαν|απαντ|καλυπτ)\w*")
_BUT = re.compile(r"\b(?:αλλα|ομως|ωστοσο|παρ'?\s*ολα)\b")
YEAR = re.compile(r"\b(18[2-9]\d|19\d\d)\b")
CITATION_REACH = 120   # a quote's citation must follow within this many characters (or precede it in the sentence)


def _numbers(marker):
    """'1, 3' -> [1, 3]; '2-4' -> [2, 3, 4]."""
    out = []
    for part in re.split(r"\s*[,;]\s*", marker):
        if re.search(r"[–-]", part):
            a, b = (int(x) for x in re.split(r"\s*[–-]\s*", part))
            out += list(range(a, b + 1)) if 0 < b - a < 20 else [a, b]
        else:
            out.append(int(part))
    return out


def comparable(text):
    """Text reduced for comparison: normalised, lowercase, no accents, words only, single spaces."""
    return " ".join(re.sub(r"[^\w]+", " ", fold(normalize(text))).split())


def quote_found(quote, chunk_text):
    """True if every piece of the quote (split at "…") appears in the chunk text, in order."""
    haystack, pos = comparable(chunk_text), 0
    for piece in ELLIPSIS.split(quote):
        piece = comparable(piece)
        if not piece:
            continue
        i = haystack.find(piece, pos)
        if i < 0:
            return False
        pos = i + len(piece)
    return True


def closest(quote, chunk_text):
    """(similarity 0-1, passage): the stretch of the chunk most like the quote, word by word. Shown when a quote
    fails, to tell a quote with small changes (0.9) from one that isn't in the text at all."""
    q = comparable(ELLIPSIS.sub(" ", quote)).split()
    words = chunk_text.split()
    plain = [comparable(w) for w in words]
    best = (0.0, "")
    for size in {max(1, len(q) + d) for d in (-4, -2, 0, 2, 4, 6, 8)}:     # the model may drop or add words
        for i in range(0, max(1, len(words) - size + 1)):
            ratio = difflib.SequenceMatcher(None, q, plain[i:i + size], autojunk=False).ratio()
            if ratio > best[0]:
                best = (ratio, " ".join(words[i:i + size]))
    return best


_SENTENCE_BREAK = re.compile(r"([.;!?])\s+(?=[«(\"“*]?[Α-ΩΆ-ΏA-Z0-9])")


def _sentences(text):
    """Sentences and list items. A full stop after a short word or an abbreviation ("Α.Ν. 539", "παρ. 2")
    doesn't end a sentence."""
    out = []
    for line in text.split("\n"):
        start = 0
        for m in _SENTENCE_BREAK.finditer(line):
            word = re.search(r"(\S+)$", line[start:m.start()])
            w = word.group(1).strip("*«(") if word else ""
            if m.group(1) == "." and re.fullmatch(r"[^\W\d_]{1,3}|[^\W\d_.]+(?:\.[^\W\d_]+)+", w):
                continue                                   # "παρ.", "Ν.", "Α.Ν." - but not "[1]." or "1945."
            out.append(line[start:m.end()].strip())
            start = m.end()
        out.append(line[start:].strip())
    return [s for s in out if s]


def says_not_found(body):
    """The narrow test: the words the prompt asks for, near the start."""
    return bool(REFUSAL.search(body[:REFUSAL_REACH]))


def is_refusal(body):
    """Does the answer clearly say that its answer isn't in the sources? Either in the prompt's words, or in a sentence
    near the start that says so and doesn't go on with "αλλά": that sentence gives an answer after all."""
    if says_not_found(body):
        return True
    for sentence in _sentences(body[:REFUSAL_REACH]):
        folded = fold(normalize(sentence))
        match = _REFUSAL_IN_OTHER_WORDS.search(folded)
        if match and not _BUT.search(folded, match.end()):
            return True
    return False


def check(answer, chunks, closing_note=None):
    """Check an answer against its chunks (dicts with n and text). Returns a dict with ok, failures, warnings,
    citations (numbers used) and quotes (each with its citation and whether it was found)."""
    valid = {c["n"]: c for c in chunks}
    failures, warnings, quotes = [], [], []
    body = answer.replace(closing_note, " ") if closing_note else answer

    markers = [(m.start(), m.end(), _numbers(m.group(1))) for m in CITATION.finditer(body)]
    used = sorted({n for _, _, ns in markers for n in ns})
    for n in used:
        if n not in valid:
            failures.append(f"[{n}] doesn't refer to a provided source (there are {len(valid)})")

    for m in QUOTE.finditer(body):
        text = next(g for g in m.groups() if g)
        if len(text.split()) < 3:                      # a quoted term, not a quotation
            continue
        sentence_end = _SENTENCE_BREAK.search(body, m.end())
        reach = min(m.end() + CITATION_REACH, sentence_end.start() + 1 if sentence_end else len(body))
        after = [ns for start, _, ns in markers if m.end() <= start <= reach]
        sentence_start = max(body.rfind(". ", 0, m.start()), body.rfind("\n", 0, m.start()))
        before = [ns for start, end, ns in markers if sentence_start < start and end <= m.start()]
        cited = after[0] if after else (before[-1] if before else [])
        found = [n for n in cited if n in valid and quote_found(text, valid[n]["text"])]
        entry = {"quote": text, "cited": cited, "found_in": found}
        quotes.append(entry)
        if not cited:
            failures.append(f"quote without a citation: «{text}»")
        elif not found:
            near = max((closest(text, valid[n]["text"]) for n in cited if n in valid), default=(0.0, ""))
            entry["closest"] = {"similarity": round(near[0], 2), "passage": near[1]}
            hint = f" (closest passage, {near[0]:.0%} similar: «{near[1]}»)" if near[1] else ""
            failures.append(f"quote not found in {', '.join(f'[{n}]' for n in cited)}: «{text}»{hint}")

    refusal = is_refusal(body)
    if not refusal and not used:
        failures.append("the answer cites no source")
    if not refusal:
        uncited = [s for s in _sentences(body)
                   if len(s.split()) >= 6 and not CITATION.search(s) and not s.rstrip(":").endswith("**")]
        if uncited:
            warnings.append(f"{len(uncited)} sentence(s) without a citation, e.g. \"{uncited[0][:120]}\"")
        if not YEAR.search(body):
            warnings.append("no year named (the law and its year should be named)")
    if closing_note and closing_note not in answer:
        warnings.append("closing note missing")

    return {"ok": not failures, "refusal": refusal, "citations": used, "quotes": quotes,
            "failures": failures, "warnings": warnings}
