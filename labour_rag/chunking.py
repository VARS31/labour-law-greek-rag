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

MIN_WORDS = 20
MAX_WORDS = 500
OVERLAP = 50
STUB_WORDS = 30
TITLE_WORDS_IN_HEADER = 12

# "1.Τα σκάφη", "2) Η αμοιβή", "3. «Οι …»": a number at the start of a sentence, then a capital.
_PARAGRAPH = re.compile(r"(?:(?<=\s)|^|(?<=[.:;·»)]))(\d{1,2})\s?([.)])\s?(?=[«(\"“]?[Α-ΩΆ-Ώ])")
# Numbered lists before the decision formula are recitals ("Έχοντας υπόψη: 1.Τις διατάξεις …"), not the body.
_DECISION = re.compile(r"(?:αποφασίζ\w*|αποφασίσαμεν|εγκρίνο\w*|ορίζο\w*|διατάσσο\w*|κηρύσσο\w*)\s*:")
_NOTE = re.compile(r"\(|(?:Κατηργήθη|Καταργήθηκ|Τροποποιήθηκ|Τροποποιηθ|Ετροποποιήθη|Αντικατεστάθη|Αντικαταστάθηκ"
                   r"|Συμπληρώθηκ|Συνεπληρώθη|Περιελήφθη|Ανεστάλη|Παραλείπ|Βλ\.|Ίδε)")
_REPEAL = re.compile(r"\b(?:[Κκ]ατηργήθη(?:σαν)?|[Κκ]αταργήθηκ(?:ε|αν)|[Κκ]αταργηθ(?:είς|έν|έντα|είσα|είσαι))\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[«(]?[Α-ΩΆ-Ώ])")
_LEADING_PARAGRAPH_NO = re.compile(r"^\s*\d{1,2}\s?[.)]\s?")
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


def repeal_sentences(text):
    """Sentences saying the act (or part of it) was repealed: "Κατηργήθη δια του άρθρ. 12 Α.Ν. 1836/1951 …"."""
    return [s.strip()[:400] for s in _SENTENCE_SPLIT.split(text) if _REPEAL.search(s)]


def _short_title(title):
    if not title:
        return None
    words = title.split()
    return " ".join(words[:TITLE_WORDS_IN_HEADER]) + ("…" if len(words) > TITLE_WORDS_IN_HEADER else "")


def chunk_document(doc, text, meta):
    """Chunk records for one document. `doc` has doc_id/split/labels, `text` is the cleaned text,
    `meta` comes from header.parse_header."""
    method, pieces = split_document(text)
    pieces = merge_small(pieces)
    is_stub = len(text.split()) < STUB_WORDS
    cite, short_title = citation(meta), _short_title(meta.get("title"))
    records = []
    for piece in pieces:
        is_note = bool(_NOTE.match(_body(piece, meta) or "x"))
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
