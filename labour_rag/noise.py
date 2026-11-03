"""Remove printed-page noise from Raptarchis texts.

The source is a loose-leaf book, and its page headers ended up in the middle of sentences:

    "… από 1 (Αντί για τη σελ. 91(θ) Σελ. 91(ι) Τεύχος 1294-Σελ. 33 Ασφάλιση κατά της Ανεργίας
     Οργ/σμός Απασ/σης Εργατ/κού Δυν/κού (Ο.Α.Ε.Δ.) 15.Γ .β.20 Ιανουαρίου έως 30 Απριλίου …"

A header block is built from anchors (replacement note, page, update issue, book position code), running
titles and bare page numbers. Anchors have a fixed shape and are always removed. Running titles are ordinary
Greek words, so a title is removed only when it is on a list learned from the corpus (see
`learn_running_titles`) and sits right next to an anchor. Unknown words are never removed.
"""

import collections
import re

from .normalize import fold

_PAGE_NO = r"(?:\d+(?:\s?,\s?\d+)?(?:\s?\([α-ω]{1,2}\))?|[ΙVXΧ]{1,5}(?![^\W\d_]))"  # 91 / 306,846 / 57(β) / ΙΙ
ANCHORS = {
    # "(Αντί για τη σελ. 91(θ)", "(Μετά την σελ. 362,34)", "(Αντί των σελ. 103(α), 104,01 και 105)"
    "replacement_note": rf"\((?:Αντί|Μετά)\s+(?:για\s+)?(?:τη|την|της|των|το|του)?\s*σελ(?:\.|ίδα|ίς)\s?{_PAGE_NO}"
                        rf"(?:\s?(?:,|και)\s?{_PAGE_NO})*\)?",
    # "Τεύχος 1294-Σελ. 33", "Τεύχος ΙΒ-1-3Σελ. 37", "Τεύχος 1292 - Σελ. 82", "Τεύχος1109", "Τεύχος ΙΑ 7-"
    "issue": r"Τεύχος\s*(?:[Α-Ω]{1,3}\s?[-–]?\s?)?\d+(?:[-–]\d+)*(?:\s?[-–])?(?:\s?Σελ(?:\.|ίς)?\s?\d*)?",
    # "Σελ. 228", "Σελίς 307", "Σελ.306,938", "Σελ. 30,207(α)", "Σελ., 30,289"; lowercase "σελ." is a
    # cross-reference ("ανωτ. σελ. 306,823") and is kept
    "page": rf"Σελ(?:\.|ίς|ίδα),?\s?{_PAGE_NO}",
    # "15.Λ.α.58", "15.Γ .β.20", "15.Α.βα.6-7", "15.Β.β.31-32", "15.Λ.α.6α", "15.Γ .β.20α-20β", "15.Δ.ζ-η.12"
    "position_code": r"(?<![\w.])\d{1,2}\s?\.\s?[Α-Ω][α-ω]?\s?\.\s?[α-ω]{1,2}(?:\s?[-–]\s?[α-ω]{1,2})?\s?\.\s?\d+"
                     r"(?:[α-ω](?=[\s\-–]|$))?(?:\s?[-–]\s?\d+(?:[α-ω](?=\s|$))?)?",
}
_ANCHOR = re.compile("|".join(f"(?P<{name}>{rx})" for name, rx in ANCHORS.items()))
# A bare page number next to a header part: "451", "- 151", "183-75", "117(α)", "-254,19(β)".
# Not "751/1948", "2.5" or "20%" (must be followed by a space or the end).
_DIGITS = r"(?:[-–]\s?)?\d{1,4}(?:\s?,\s?\d{1,3})?(?:\s?[-–]\s?\d{1,4})?(?:\([α-ω]{1,2}\))?"
# Front-matter pages are numbered with Greek numerals ("ΙΣΤ" = 16, "ΝΔ" = 54, "ΞΓ-75"). Those look like
# short capital words, so they are only taken where more header follows.
_GREEK_NUMERAL = r"(?:[ΡΣΤΥΦΧΨΩ]?[ΙΚΛΜΝΞΟΠ]?(?:ΣΤ|[ΑΒΓΔΕΖΗΘ])?)(?:[-–]\d{1,4})?"
_NUMBER = re.compile(rf"\s*{_DIGITS}(?=\s|$)")
_NUMERAL = re.compile(rf"\s*(?=[Α-Ω]){_GREEK_NUMERAL}(?=\s|$)")
_NUMBER_TOKEN = re.compile(rf"{_DIGITS}|{_GREEK_NUMERAL}|[-–]")
_WORD = re.compile(r"\S+")
MAX_TITLE_WORDS = 16


def _looks_like_title(words):
    """A running title starts with a capital, has a real word in it and is not itself page furniture."""
    return (1 <= len(words) <= MAX_TITLE_WORDS and words[0][:1].isupper()
            and any(sum(c.isalpha() for c in w) >= 4 for w in words)
            and not re.match(r"(?:Τεύχος|Σελ|Άρθρ|Αρθρ)", words[0]))


def learn_running_titles(texts, min_count=2):
    """Running titles = text found *between* two header anchors (page numbers dropped), seen at least
    `min_count` times in the corpus. Returns {folded title: example spelling}."""
    counts, spelling = collections.Counter(), {}
    for text in texts:
        anchors = list(_ANCHOR.finditer(text))
        for a, b in zip(anchors, anchors[1:]):
            gap = text[a.end():b.start()].split()
            while gap and _NUMBER_TOKEN.fullmatch(gap[0]):
                gap.pop(0)
            while gap and _NUMBER_TOKEN.fullmatch(gap[-1]):
                gap.pop()
            if _looks_like_title(gap):
                key = fold(" ".join(gap))
                counts[key] += 1
                spelling.setdefault(key, " ".join(gap))
    return {k: spelling[k] for k, n in counts.items() if n >= min_count}


def label_titles(names, titles):
    """Label names (chapter/subject) not already learned, as weak titles: {folded: spelling}."""
    return {fold(n): n for n in names if fold(n) not in titles}


def _match_title_after(text, pos, titles):
    """End offset of the longest known title starting at `pos` (after spaces), or None."""
    words = []
    for m in _WORD.finditer(text, pos):
        words.append(m)
        if len(words) == MAX_TITLE_WORDS:
            break
    for n in range(len(words), 0, -1):
        if fold(" ".join(w.group() for w in words[:n])) in titles:
            return words[n - 1].end()
    return None


def _match_title_before(text, pos, titles):
    """Start offset of the longest known title ending at `pos`, or None."""
    words = list(_WORD.finditer(text, max(0, pos - 300), pos))[-MAX_TITLE_WORDS:]
    for n in range(len(words), 0, -1):
        if fold(" ".join(w.group() for w in words[-n:])) in titles:
            return words[-n].start()
    return None


_SPACE = re.compile(r"\s*")
_NUMBER_BEFORE = re.compile(r"(?:^|\s)((?:[-–]\s?)?\d{2,4}(?:-\d{1,4})?)\s*$")


def _skip_space(text, pos):
    return _SPACE.match(text, pos).end()


def strip_page_noise(text, titles, weak_titles=()):
    """Return (clean text, removed blocks). A block is {"text", "parts": Counter, "rejoined": bool}.

    `titles` (learned from the corpus) are removed wherever they touch a header part. `weak_titles` (label
    names) can also be real headings ("Καταγγελία συμβάσεως εργασίας (Αριθ. υποδείγμ. 1)" is a form), so
    they are removed only when more header follows them.
    "rejoined" means the block cut a word in two ("υπαλ[block] ληλικής") and the halves were glued back.
    """
    blocks, segments, pos = [], [], 0
    for anchor in _ANCHOR.finditer(text):
        if anchor.start() < pos:            # already swallowed by the previous block
            continue
        parts = collections.Counter({anchor.lastgroup: 1})
        start, end, last = anchor.start(), anchor.end(), anchor.lastgroup

        # Extend to the right: anchors, known titles and page numbers, in any order.
        while True:
            nxt = _ANCHOR.match(text, _skip_space(text, end))
            if nxt:
                parts[nxt.lastgroup] += 1
                end, last = nxt.end(), nxt.lastgroup
                continue
            title_end = _match_title_after(text, end, titles)
            if not title_end and weak_titles:
                weak_end = _match_title_after(text, end, weak_titles)
                if weak_end and (_ANCHOR.match(text, _skip_space(text, weak_end)) or _NUMBER.match(text, weak_end)):
                    title_end = weak_end
            if title_end:
                parts["running_title"] += 1
                end, last = title_end, "running_title"
                continue
            # A number right after a code or title is a page number. Elsewhere (after a bare "Σελ. N") it could
            # be real text, so it is only taken when more header follows it. Greek numerals always need that.
            number = _NUMBER.match(text, end)
            numeral = None if number else _NUMERAL.match(text, end)
            candidate = number or numeral
            if candidate and candidate.end() > end and (
                    (number and last in ("position_code", "running_title"))
                    or _ANCHOR.match(text, _skip_space(text, candidate.end()))
                    or _match_title_after(text, candidate.end(), titles)):
                parts["page_number"] += 1
                end, last = candidate.end(), "page_number"
                continue
            break

        # A block that starts with a code may have a known title and a page number just before it
        # ("441 15.Β.β.1", "Απαγόρευση χρήσης επιβλαβών ουσιών 15.Λ.β.1-3"). Single digits are kept,
        # because they are usually real text ("από 1 (Αντί για τη σελ. …").
        if anchor.lastgroup == "position_code":
            title_start = _match_title_before(text, start, titles)
            if title_start is not None and title_start >= pos:
                parts["running_title"] += 1
                start = title_start
            number = _NUMBER_BEFORE.search(text, pos, start)
            if number:
                parts["page_number"] += 1
                start = number.start(1)

        segments.append(text[pos:start])
        after = _skip_space(text, end)
        rejoined = start > 0 and text[start - 1].isalpha() and text[after:after + 1].islower()
        blocks.append({"text": text[start:end], "parts": parts, "rejoined": rejoined})
        pos = end
    segments.append(text[pos:])

    clean = segments[0]
    for block, segment in zip(blocks, segments[1:]):
        clean = clean.rstrip() + ("" if block["rejoined"] else " ") + segment.lstrip()
    return re.sub(r"\s{2,}", " ", clean).strip(), blocks
