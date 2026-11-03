"""Split one cleaned document into labelled chunks.

Method per document, in order of preference:
  article    split at article markers; the header/preamble before the first marker is its own chunk
  paragraph  no markers, but numbered paragraphs (1. 2. 3. or 1) 2) 3)) after the decision formula
  size       neither, and longer than MAX_WORDS: cut into overlapping windows
  whole      neither, and short: the document is one chunk
Then pieces under MIN_WORDS are merged into the previous piece, and pieces over MAX_WORDS are cut into
windows of at most MAX_WORDS with about OVERLAP words shared between neighbours.
"""

import math
import re
from dataclasses import dataclass, field

from .articles import ARTICLE, describe, find_markers
from .header import citation
from .normalize import fold

MIN_WORDS = 20
MAX_WORDS = 500
OVERLAP = 50
STUB_WORDS = 30
TITLE_WORDS_IN_HEADER = 12

# "1.Τα σκάφη", "2) Η αμοιβή", "3. «Οι …»": a number at the start of a sentence, then a capital.
_PARAGRAPH = re.compile(r"(?:(?<=\s)|^|(?<=[.:;·»)]))(\d{1,2})\s?([.)])\s?(?=[«(\"“]?[Α-ΩΆ-Ώ])")
# Numbered lists before the decision formula are recitals ("Έχοντας υπόψη: 1.Τις διατάξεις …"), not the body.
_DECISION = re.compile(r"(?:αποφασίζ\w*|αποφασίσαμεν|εγκρίνο\w*|ορίζο\w*|διατάσσο\w*|κηρύσσο\w*)\s*:")
_NOTE = re.compile(r"\(|(?:(?:Επίσης|Ομοίως|Εν συνεχεία|Κατόπιν)\s+)?"           # "Επίσης τροποποιήθηκε …"
                   r"(?i:κατηργήθη|καταργήθηκ|τροποποιήθηκ|τροποποιηθ|ετροποποιήθη|αντικατεστάθη|αντικαταστάθηκ"
                   r"|συμπληρώθηκ|συνεπληρώθη|περιελήφθη|ανεστάλη|παραλείπ|εκδόθηκ|εξεδόθ|βλ\.|ίδε)")
_REPEAL = re.compile(r"\b(?:[Κκ]ατηργήθη(?:σαν)?|[Κκ]αταργήθηκ(?:ε|αν)|[Κκ]αταργηθ(?:είς|έν|έντα|είσα|είσαι))\b")
# Possible end of a sentence: "." or ";" followed by the end, a capital, a quote/bracket, a paragraph number
# ("2.Η") or a list item ("δ)Τμήμα"). Not "παρ. 3 άρθρ.", "Απρ. 1987" or "αριθ. 9)".
_SENTENCE_END = re.compile(r"[.;](?=\s*$|\s+(?:[«(\"“]?[Α-ΩΆ-Ώ]|\d{1,2}\s?[.)]\s?[«(]?[Α-ΩΆ-Ώ]|[α-ω]{1,2}\)))")
# A full stop after one of these (accents removed) is an abbreviation, not the end of a sentence:
# "Πράξεως Υπουργ. Συμβουλίου", "Απόφ. Υπ. Εργασίας". Any word of 3 letters or fewer ("Ν.", "απ.", "Υπ.",
# "κλπ.") counts as an abbreviation too; Greek sentences almost never end on one.
_ABBREVIATIONS = {
    "υπουργ", "κυβερν", "συμβ", "συμβουλ", "κοιν", "κοινων", "ασφαλ", "εργασ", "οικον", "οικονομ", "διοικ",
    "αποφ", "αριθ", "αρθρ", "τομ", "ανωτ", "κατωτ", "εδαφ", "στοιχ", "διορθ", "ημαρτ", "πολιτ", "δικον",
    "δραχ", "φεβρ", "μαρτ", "ιουν", "ιουλ", "σεπτ", "νοεμ",
}
_MAX_SHORT_ABBREVIATION = 3
_WORD_BEFORE = re.compile(r"([^\W\d_]+)$")
_LIST_ITEM = re.compile(r"(?<![^\W\d_])[α-ω]{1,2}\)")
_LEADING_PARAGRAPH_NO = re.compile(r"^\s*\d{1,2}\s?[.)]\s?")
_PARAGRAPH_NO = re.compile(r"\d{1,2}\s?[.)]\s?")      # same, for .match(text, pos): "^" never matches at pos > 0
_NOTE_GAP = re.compile(r"[\s.,;:–-]*")                 # what may sit between two notes: "). 2.(…"
NOTE_SHARE = 0.5          # a chunk is a note when the note covers at least half of its body
NOTE_BRACKET_WORDS = 60   # a note bracket that doesn't close within this many words lost its ")"
REPEAL_WORDS_BEFORE = 15
REPEAL_WORDS_AFTER = 25
# In the editors' style the heading of an article comes *before* its marker:
# "… οδηγεί η κλίμαξ. Φορηταί κλίμακες Άρθρ.17.-…". After cutting at markers, that heading (sometimes with a
# chapter heading: "ΚΕΦΑΛΑΙΟ Γ΄ ΥΠΟΧΡΕΩΣΕΙΣ ΤΩΝ ΕΡΓΟΔΟΤΩΝ Γενικές υποχρεώσεις") is the unfinished tail
# of the previous piece. It is moved to the piece it belongs to.
_TRAILING_HEADING = re.compile(r"(?<=[.;:»)])\s+([Α-ΩΆ-Ώ«][^.;:]{0,200})$")
MAX_HEADING_WORDS = 15


@dataclass
class Piece:
    text: str
    kind: str                        # preamble | article | paragraph | whole | size
    labels: list = field(default_factory=list)
    numbers: list = field(default_factory=list)

    @property
    def words(self):
        return len(self.text.split())


def _paragraph_chain(text):
    """Start offsets of the longest run of numbered paragraphs 1, 2, 3, … (same style), or []."""
    decision = _DECISION.search(text)
    start = decision.end() if decision else 0
    cands = [(int(m.group(1)), m.group(2), m.start()) for m in _PARAGRAPH.finditer(text, start)]
    best = []
    for i, (n, style, pos) in enumerate(cands):
        if n != 1:
            continue
        chain, want = [pos], 2
        for n2, style2, pos2 in cands[i + 1:]:
            if n2 == want and style2 == style:
                chain.append(pos2)
                want += 1
        if len(chain) > len(best):
            best = chain
    return best if len(best) >= 2 else []


def _cut(text, starts):
    bounds = [0, *starts, len(text)]
    return [text[a:b].strip() for a, b in zip(bounds, bounds[1:])]


def move_trailing_headings(pieces):
    """Move a heading stuck at the end of a piece to the start of the next one. Returns how many moved."""
    moved = 0
    for prev, nxt in zip(pieces, pieces[1:]):
        m = _TRAILING_HEADING.search(prev.text)
        if m and len(m.group(1).split()) <= MAX_HEADING_WORDS:
            prev.text = prev.text[:m.start()].rstrip()
            nxt.text = f"{m.group(1).strip()} {nxt.text}"
            moved += 1
    return moved


def split_document(text, stats=None):
    """(method, pieces) before merging and size splitting. `stats` (a Counter) gets "headings_moved"."""
    stats = stats if stats is not None else {}
    markers = find_markers(text)
    if markers:
        segments = _cut(text, [m.start() for m in markers])
        pieces = [Piece(segments[0], "preamble", ["Προοίμιο"])] if segments[0] else []
        for m, segment in zip(markers, segments[1:]):
            label, numbers = describe(m)
            pieces.append(Piece(segment, "article", [label], numbers))
        stats["headings_moved"] = stats.get("headings_moved", 0) + move_trailing_headings(pieces)
        return "article", pieces

    chain = _paragraph_chain(text)
    if chain:
        segments = _cut(text, chain)
        pieces = [Piece(segments[0], "preamble", ["Προοίμιο"])] if segments[0] else []
        pieces += [Piece(s, "paragraph", [f"παρ. {i}"], [i]) for i, s in enumerate(segments[1:], 1)]
        stats["headings_moved"] = stats.get("headings_moved", 0) + move_trailing_headings(pieces)
        return "paragraph", pieces

    if len(text.split()) > MAX_WORDS:
        return "size", [Piece(text, "size")]
    return "whole", [Piece(text, "whole")]


def merge_small(pieces, min_words=MIN_WORDS):
    """Pieces under `min_words` join the previous piece; a short first piece joins the next one."""
    merged = []
    for piece in pieces:
        if merged and piece.words < min_words:
            prev = merged[-1]
            merged[-1] = Piece(f"{prev.text} {piece.text}", prev.kind, prev.labels + piece.labels,
                               prev.numbers + piece.numbers)
        else:
            merged.append(piece)
    if len(merged) > 1 and merged[0].words < min_words:
        first, second = merged[0], merged[1]
        merged[:2] = [Piece(f"{first.text} {second.text}", second.kind, first.labels + second.labels,
                            first.numbers + second.numbers)]
    return merged


def split_words(words, max_words=MAX_WORDS, overlap=OVERLAP):
    """Equal windows of at most `max_words`, neighbours sharing about `overlap` words."""
    if len(words) <= max_words:
        return [words]
    n = math.ceil((len(words) - overlap) / (max_words - overlap))
    size = math.ceil((len(words) - overlap) / n) + overlap
    starts = [round(i * (len(words) - size) / (n - 1)) for i in range(n)]
    return [words[s:s + size] for s in starts]


def _body(piece, meta):
    """The text after the marker (article/paragraph) or after the title (preamble/whole)."""
    text = piece.text
    if piece.kind == "article":
        m = ARTICLE.search(text)                       # the marker may follow a moved heading
        text = text[m.end():] if m else re.sub(r"^\S+\s+\S+", "", text)
    elif piece.kind in ("preamble", "whole", "size") and meta.get("title"):
        i = text.find(meta["title"])
        text = text[i + len(meta["title"]):] if i >= 0 else text
    text = _LEADING_PARAGRAPH_NO.sub("", text.lstrip(" .-–"))
    return text.strip()


def _closing_bracket(text, start):
    """Index just after the ")" that closes the "(" at `start`, or None if it never closes."""
    depth = 0
    for i in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return i + 1
    return None


def _sentence_ends(text, start=0):
    """Offsets just after each real sentence end from `start` on."""
    for m in _SENTENCE_END.finditer(text, start):
        if m.group() == ".":
            word = _WORD_BEFORE.search(text, max(0, m.start() - 20), m.start())
            if word and (len(word.group(1)) <= _MAX_SHORT_ABBREVIATION or fold(word.group(1)) in _ABBREVIATIONS):
                continue
        yield m.end()


def _sentence_end(text, start):
    return next(_sentence_ends(text, start), len(text))


def note_words(body):
    """How many words at the start of `body` are editorial notes.

    A note is a bracket ("(Καταργήθηκαν από …)") or a sentence starting with an editorial verb ("Κατηργήθη
    δια …", "Ετροποποιήθη δια των: α)… β)…"). Consecutive notes are counted together, and so are the list
    items a note introduces with a colon. A bracket that doesn't close within NOTE_BRACKET_WORDS words lost
    its ")" in the source; it counts only up to the end of its first sentence.
    """
    pos, in_list = 0, False
    while True:
        rest_start = _NOTE_GAP.match(body, pos).end()
        lead = _PARAGRAPH_NO.match(body, rest_start)
        start = lead.end() if lead else rest_start
        if start >= len(body):
            break
        if not (_NOTE.match(body, start) or (in_list and _LIST_ITEM.match(body, start))):
            break
        end = _closing_bracket(body, start) if body[start] == "(" else None
        if end and len(body[start:end].split()) > NOTE_BRACKET_WORDS:
            end = None
        end = end or _sentence_end(body, start)
        in_list = in_list or ":" in body[start:end]
        pos = end
    return len(body[:pos].split())


def repeal_sentences(text):
    """The short sentence around each past-tense repeal verb: "(Καταργήθηκαν από την παρ. 3 άρθρ. 17 …)".

    It starts at the sentence start, a colon or a still-open bracket (at most REPEAL_WORDS_BEFORE words back)
    and ends at the sentence end or the closing bracket (at most REPEAL_WORDS_AFTER words on)."""
    out = []
    words = list(re.finditer(r"\S+", text))
    for m in _REPEAL.finditer(text):
        before = [w for w in words if w.end() <= m.start()]
        start = before[-REPEAL_WORDS_BEFORE].start() if len(before) >= REPEAL_WORDS_BEFORE else 0
        cut_left = len(before) > REPEAL_WORDS_BEFORE
        boundaries = [e for e in _sentence_ends(text, start) if e <= m.start()]
        boundaries += [i + 1 for i in range(start, m.start()) if text[i] == ":"]
        boundaries += [i.start() for i in _LIST_ITEM.finditer(text, start, m.start())]
        boundaries += [i for i in range(start, m.start())             # a bracket still open at the verb
                       if text[i] == "(" and (_closing_bracket(text, i) or len(text) + 1) > m.start()]
        if boundaries:
            start, cut_left = max(boundaries), False
        end = _sentence_end(text, m.end())
        if text[start:start + 1] == "(":                       # a bracketed note ends at its ")"
            end = min(end, _closing_bracket(text, start) or end)
        after = list(re.finditer(r"\S+", text[m.end():end]))
        cut_right = len(after) > REPEAL_WORDS_AFTER
        if cut_right:
            end = m.end() + after[REPEAL_WORDS_AFTER - 1].end()
        sentence = ("…" if cut_left else "") + text[start:end].strip() + ("…" if cut_right else "")
        if sentence not in out:
            out.append(sentence)
    return out


def _short_title(title):
    if not title:
        return None
    words = title.split()
    return " ".join(words[:TITLE_WORDS_IN_HEADER]) + ("…" if len(words) > TITLE_WORDS_IN_HEADER else "")


def source(meta, chapter):
    """How a chunk names its source. With act type and number: the citation ("Ν. 2994/1922"). Otherwise
    the fallback: act type, title, chapter and year ("Π.Δ. «Περί υγιεινής …» (ΥΓΙΕΙΝΗ …, 1934)").
    Returns (text, used_fallback)."""
    if meta.get("act_abbr") and meta.get("act_number"):
        return citation(meta), False
    title = _short_title(meta.get("title"))
    where = ", ".join(str(x) for x in (chapter, meta.get("year")) if x)
    parts = [meta.get("act_abbr"), f"«{title}»" if title else None, f"({where})" if where else None]
    return " ".join(p for p in parts if p), True


def chunk_document(doc, text, meta):
    """Chunk records for one document. `doc` has doc_id/split/labels, `text` is the cleaned text,
    `meta` comes from header.parse_header."""
    method, pieces = split_document(text)
    pieces = merge_small(pieces)
    is_stub = len(text.split()) < STUB_WORDS
    cite, fallback = source(meta, doc["chapter"])
    short_title = None if fallback else _short_title(meta.get("title"))   # the fallback already holds it
    records = []
    for piece in pieces:
        body = _body(piece, meta)
        is_note = bool(body) and note_words(body) >= NOTE_SHARE * len(body.split())
        windows = split_words(piece.text.split())
        for part, words in enumerate(windows, 1):
            chunk_text = " ".join(words)
            label = ", ".join(piece.labels) or None
            shown = label
            if len(windows) > 1:
                shown = f"{label} (μέρος {part}/{len(windows)})" if label else f"μέρος {part}/{len(windows)}"
            header = ", ".join(x for x in (cite, shown, short_title) if x)
            records.append({
                "id": f"glc-{doc['doc_id']:05d}-{len(records):03d}",
                "doc_id": doc["doc_id"],
                "seq": len(records),
                "split": doc["split"],
                "volume": doc["volume"],
                "chapter": doc["chapter"],
                "subject": doc["subject"],
                "act_type": meta.get("act_type"),
                "act_abbr": meta.get("act_abbr"),
                "act_number": meta.get("act_number"),
                "year": meta.get("year"),
                "fek": meta.get("fek"),
                "title": meta.get("title"),
                "citation": cite,
                "citation_fallback": fallback,
                "method": method,
                "kind": piece.kind,
                "article": label,
                "article_numbers": piece.numbers,
                "part": part,
                "parts": len(windows),
                "words": len(words),
                "is_stub": is_stub,
                "is_note": is_note,
                "repeal_sentences": repeal_sentences(chunk_text),
                "text": chunk_text,
                "embed_text": f"{header}\n{chunk_text}" if header else chunk_text,
            })
    return records
