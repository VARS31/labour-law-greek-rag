"""Phase 1A: clean and chunk the labour-law volume (41) of the Greek Legal Code.

Writes data/processed/labour_chunks.jsonl, data/processed/running_titles.json and docs/chunking-report.md.
No AI, no embeddings, no database.

Usage:
    .venv/bin/python -I scripts/build_chunks.py [RAW_DIR]
"""

import collections
import json
import random
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # -I leaves the repo off sys.path

from labour_rag import normalize as norm_mod  # noqa: E402
from labour_rag.chunking import MAX_WORDS, MIN_WORDS, OVERLAP, STUB_WORDS, merge_small, split_document, split_words  # noqa: E402
from labour_rag.chunking import NOTE_SHARE, _body, _short_title, chunk_document, note_words  # noqa: E402
from labour_rag.dataset import LABOUR_VOLUME, load_documents  # noqa: E402
from labour_rag.header import citation, parse_header  # noqa: E402
from labour_rag.noise import label_titles, learn_running_titles, strip_page_noise  # noqa: E402
from labour_rag.normalize import normalize, normalize_with_counts  # noqa: E402

PHASE0_ESTIMATE = 5301
SEED = 42

# The Phase 1A rules, kept only to show before/after numbers in the report's "Fixes in Phase 1B" section.
_OLD_NOTE = re.compile(r"\(|(?:Κατηργήθη|Καταργήθηκ|Τροποποιήθηκ|Τροποποιηθ|Ετροποποιήθη|Αντικατεστάθη|"
                       r"Αντικαταστάθηκ|Συμπληρώθηκ|Συνεπληρώθη|Περιελήφθη|Ανεστάλη|Παραλείπ|Βλ\.|Ίδε)")
_OLD_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[«(]?[Α-ΩΆ-Ώ])")
_REPEAL_VERB = re.compile(r"\b(?:[Κκ]ατηργήθη(?:σαν)?|[Κκ]αταργήθηκ(?:ε|αν)|[Κκ]αταργηθ(?:είς|έν|έντα|είσα|είσαι))\b")


def old_repeal_sentences(text):
    return [s.strip()[:400] for s in _OLD_SENTENCE_SPLIT.split(text) if _REPEAL_VERB.search(s)]


def old_header(record, meta):
    """The Phase 1A embed header: citation (if any), article, short title."""
    shown = record["article"]
    if record["parts"] > 1:
        shown = f"{shown} (μέρος {record['part']}/{record['parts']})" if shown else f"μέρος {record['part']}/{record['parts']}"
    return ", ".join(x for x in (citation(meta), shown, _short_title(meta.get("title"))) if x)


# --- markdown helpers ---------------------------------------------------------------------------
def esc(text):
    """Make chunk text safe inside a Markdown paragraph."""
    text = re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)
    return re.sub(r"^(\d+)\.", r"\1\\.", text)


def quote(text):
    return "> " + esc(text)


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


def n(x):
    return f"{x:,}"


def snippet(text, start, end, width=70):
    a, b = max(0, start - width), min(len(text), end + width)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


# --- pipeline -------------------------------------------------------------------------------------
def run(raw_dir):
    docs = load_documents(raw_dir, LABOUR_VOLUME)
    for d in docs:
        for level in ("chapter", "subject", "volume"):
            d[level] = normalize(d[level])

    norm_counts, normalized = collections.Counter(), []
    for d in docs:
        text, counts = normalize_with_counts(d["text"])
        norm_counts.update(counts)
        normalized.append(text)

    titles = learn_running_titles(normalized)
    weak = label_titles({d["chapter"] for d in docs} | {d["subject"] for d in docs}, titles)

    records, noise, per_doc = [], {"blocks": [], "parts": collections.Counter()}, []
    noise["headings"] = collections.Counter()
    for d, text in zip(docs, normalized):
        clean, blocks = strip_page_noise(text, titles, weak)
        for b in blocks:
            noise["parts"].update(b["parts"])
            noise["blocks"].append((d["doc_id"], text, b))
        meta = parse_header(clean)
        method, pieces = split_document(clean, noise["headings"])
        merged = merge_small(pieces)
        chunks = chunk_document(d, clean, meta)
        # Before/after of the Phase 1B fixes. Records come out piece by piece, window by window.
        i = 0
        for piece in merged:
            body = _body(piece, meta)
            for _ in split_words(piece.text.split()):
                r = chunks[i]
                noise.setdefault("fixes", []).append({
                    "id": r["id"], "words": r["words"], "new_note": r["is_note"],
                    "old_note": bool(_OLD_NOTE.match(body or "x")),
                    "note_share": note_words(body) / max(1, len(body.split())),
                    "old_repeal": old_repeal_sentences(r["text"]), "new_repeal": r["repeal_sentences"],
                    "old_header": old_header(r, meta), "new_header": r["embed_text"].split("\n")[0],
                    "fallback": r["citation_fallback"], "text": r["text"]})
                i += 1
        records.extend(chunks)
        per_doc.append({"doc": d, "raw": d["text"], "normalized": text, "clean": clean, "meta": meta,
                        "method": method, "pieces": len(pieces), "merged": len(pieces) - len(merged),
                        "windows_added": sum(len(split_words(p.text.split())) - 1 for p in merged),
                        "chunks": chunks})
    return docs, normalized, norm_counts, titles, weak, noise, per_doc, records


# --- report sections ------------------------------------------------------------------------------
def normalisation_examples(docs):
    """Two before/after examples per normalisation step, found in the raw labour texts."""
    finders = {
        "micro sign µ → μ": r"µ",
        "spacing tonos + vowel → accented vowel": norm_mod._SPACING_TONOS.pattern,
        "split capital words joined": r"(?<![^\W\d_])[Α-Ω]*(?:[Α-Ω]Γ|[ΓΠΤΚΒΦΧΘΔ]Ρ) Α[Α-Ω]+",
        "Latin look-alikes inside Greek words": r"\b(?=\w*[A-Za-z])(?=\w*[Ͱ-Ͽ])\w+",
        "Symbol-font characters": r"[-]+(?:\s[-]+)*",
        "number glued to a word split": r"\d(?=[Α-ΩΆ-Ώ][α-ωά-ώ])",
    }
    out = {}
    for name, rx in finders.items():
        found = []
        for d in docs:
            for m in re.finditer(rx, d["text"]):
                before = snippet(d["text"], m.start(), m.end(), 25)
                after = normalize(before)
                if after != before.strip() and len(found) < 2:
                    # private-use characters are invisible, so show their code points
                    visible = re.sub("[-]", lambda c: f"⟨{ord(c.group()):04X}⟩", before)
                    found.append((visible, after))
            if len(found) >= 2:
                break
        out[name] = found
    return out


def strangeness(records):
    """Pick three odd chunks: most symbol-heavy, longest unbroken token, biggest backwards article jump."""
    def symbol_share(r):
        t = r["text"]
        return sum(not (c.isalpha() or c.isspace() or c in ".,;:·()«»\"'’-–") for c in t) / max(1, len(t))

    def longest_word(r):
        return max(re.findall(r"[^\W\d_]+", r["text"]) or [""], key=len)

    symbols = max((r for r in records if r["words"] >= 20), key=symbol_share)
    token = max(records, key=lambda r: len(longest_word(r)))
    jump, worst = 0, None
    by_doc = collections.defaultdict(list)
    for r in records:
        by_doc[r["doc_id"]].append(r)
    for chunks in by_doc.values():
        prev = None
        for r in chunks:
            if r["kind"] == "article" and r["article_numbers"] and r["part"] == 1:
                if prev is not None and prev - r["article_numbers"][0] > jump:
                    jump, worst = prev - r["article_numbers"][0], r
                prev = r["article_numbers"][-1]
    picks = [
        ("Strangest 1: mostly numbers and symbols",
         f"{symbol_share(symbols):.0%} of its characters are digits or symbols. Lists of references, tables "
         "and formulas end up like this after conversion. Such text embeds poorly; keyword search on the "
         "numbers will serve it better.", symbols),
        ("Strangest 2: the longest 'word'",
         f"Its longest run of letters is `{longest_word(token)}` ({len(longest_word(token))} letters): words "
         "glued together in the source. Keyword search can't find the words inside it.", token),
    ]
    if worst:
        picks.append(("Strangest 3: article numbering jumps backwards",
                      f"The article before it in the same document is {jump} numbers higher. This is the "
                      "shuffled order seen in Phase 0. The article number is kept as metadata, so search "
                      "doesn't depend on the order.", worst))
    return picks


def chunk_block(r, title=None):
    flags = [f for f in ("is_stub", "is_note") if r[f]]
    lines = [f"#### {title or r['id']}", ""] if title else [f"#### `{r['id']}`", ""]
    if title:
        lines += [f"`{r['id']}`", ""]
    lines += [
        "| Field | Value |", "|---|---|",
        f"| Document | {r['doc_id']} ({r['split']}) |",
        f"| Chapter / subject | {esc(r['chapter'])} / {esc(r['subject'])} |",
        f"| Source | {esc(r['citation'])}{' (fallback: no act number)' if r['citation_fallback'] else ''} |",
        f"| Act | {r['act_type'] or 'type not found'}, ΦΕΚ {r['fek'] or '-'} |",
        f"| Article | {esc(r['article'] or '-')} (kind: {r['kind']}, method: {r['method']}, part {r['part']}/{r['parts']}) |",
        f"| Words | {r['words']} |",
        f"| Flags | {', '.join(flags) or 'none'} |",
    ]
    if r["repeal_sentences"]:
        lines.append(f"| Repeal sentence | {esc(r['repeal_sentences'][0][:200])} |")
    lines += ["", "Text to embed:", "", quote(r["embed_text"].replace("\n", " ⏎ ")), ""]
    return "\n".join(lines)


def write_fixes(add, fixes, records):
    """Section 7: the three chunking fixes made at the start of Phase 1B, with before/after numbers."""
    by_id = {f["id"]: f for f in fixes}
    rng = random.Random(SEED)
    add("## 7. Fixes made at the start of Phase 1B\n")
    add("Three rules were tightened before loading the chunks into the database. The *before* numbers come "
        "from the Phase 1A rules, run again on the same chunks.\n")

    fallback = [f for f in fixes if f["fallback"]]
    no_type = sum(1 for r in records if r["citation_fallback"] and not r["act_abbr"])
    add("### Every chunk names its source\n")
    add(f"{n(len(fallback))} of {n(len(fixes))} chunks come from documents without an act number in the header "
        f"({n(no_type)} of them without even an act type). Their header used to start with just the article "
        "label, so the embedded text didn't say where it came from. Now it uses a fallback: act type (if known), "
        "the title in «», and the chapter and year in brackets. The same text is stored in the new `citation` "
        "field, and `citation_fallback` is `true` for these chunks.\n")
    examples = [by_id["glc-06383-019"]] if "glc-06383-019" in by_id else []
    examples += rng.sample([f for f in fallback if f not in examples], 2)
    for f in examples:
        add(f"- `{f['id']}`:")
        add(f"  - before: `{f['old_header']}`")
        add(f"  - after: `{f['new_header']}`")
    add("")

    old_notes = [f for f in fixes if f["old_note"]]
    new_notes = [f for f in fixes if f["new_note"]]
    add("### `is_note` only when the note is the main content\n")
    add(f"The old rule flagged a chunk when its text *started* with a bracket or an editorial verb. That also "
        "caught real law text that only opens with a short source reference (\"Άρθρον 18 (άρθρ. 18 Δ. 23 Νοεμ. "
        "1928, άρθρ. 7 ν. 4388). 1.Κατά τας Κυριακάς …\"), and chunks where the source lost a closing bracket. "
        f"Now the notes at the start of a chunk are measured, and the chunk is flagged only when they cover at "
        f"least {NOTE_SHARE:.0%} of it. A bracket that doesn't close within 60 words is treated as lost and "
        "counts only up to the end of its first sentence.\n")
    add("| | Before | After |\n|---|---:|---:|")
    add(f"| Chunks flagged as notes | {n(len(old_notes))} | {n(len(new_notes))} |")
    add(f"| … of which over 150 words | {n(sum(f['words'] > 150 for f in old_notes))} | "
        f"{n(sum(f['words'] > 150 for f in new_notes))} |")
    add(f"| Unflagged by the new rule | | {n(sum(f['old_note'] and not f['new_note'] for f in fixes))} |")
    add(f"| Newly flagged (e.g. \"Επίσης τροποποιήθηκε …\", \"Εκδόθηκαν: α)… β)…\") | | "
        f"{n(sum(f['new_note'] and not f['old_note'] for f in fixes))} |")
    add("")
    big = [f for f in old_notes if f["words"] > 150]
    checked = [by_id["glc-13904-015"]] if "glc-13904-015" in by_id else []
    checked += rng.sample([f for f in big if f not in checked], min(4, len(big) - len(checked)))
    add("Five of the old notes over 150 words, checked by hand (the first is the one with the lost bracket):\n")
    add("| Chunk | Words | Share that is note | Now | Start of the text |\n|---|---:|---:|---|---|")
    for f in checked:
        add(f"| `{f['id']}` | {f['words']} | {f['note_share']:.0%} | {'note' if f['new_note'] else 'law text'} | "
            f"{esc(f['text'][:150])}… |")
    add("")

    old_rep = [s for f in fixes for s in f["old_repeal"]]
    new_rep = [s for f in fixes for s in f["new_repeal"]]

    def lengths(sentences):
        w = sorted(len(s.split()) for s in sentences) or [0]
        return f"{statistics.median(w):.0f} / {pct(w, 90)} / {w[-1]}"

    add("### Repeal sentences: only the short sentence around the verb\n")
    add("The old rule kept the whole \"sentence\" around a repeal verb, but sentence ends are rare in this text, "
        "so it often grabbed a long, unrelated stretch. Now it keeps a short window: from the start of the "
        "sentence, a colon, a list item (`γ)`) or an open bracket, at most 15 words before the verb, to the end "
        "of the sentence or the closing bracket, at most 25 words after it. Abbreviations such as \"Υπουργ.\" "
        "no longer count as sentence ends.\n")
    add("| | Before | After |\n|---|---:|---:|")
    add(f"| Sentences kept | {n(len(old_rep))} | {n(len(new_rep))} |")
    add(f"| Chunks with at least one | {n(sum(bool(f['old_repeal']) for f in fixes))} | "
        f"{n(sum(bool(f['new_repeal']) for f in fixes))} |")
    add(f"| Words per sentence: median / 90% / longest | {lengths(old_rep)} | {lengths(new_rep)} |")
    add("")
    if "glc-45189-025" in by_id:
        f = by_id["glc-45189-025"]
        add("Example, `glc-45189-025`:\n")
        add(f"- before: `{esc(f['old_repeal'][0][:300])}…`" if f["old_repeal"] else "- before: (none)")
        add(f"- after: `{esc(f['new_repeal'][0])}`" if f["new_repeal"] else "- after: (none)")
        add("")


def write_report(path, docs, normalized, norm_counts, titles, weak, noise, per_doc, records):
    words = [r["words"] for r in records]
    raw_words = sum(len(d["text"].split()) for d in docs)
    norm_words = sum(len(t.split()) for t in normalized)
    clean_words = sum(len(p["clean"].split()) for p in per_doc)
    methods = collections.Counter(p["method"] for p in per_doc)
    chunks_by_method = collections.Counter(r["method"] for r in records)
    kinds = collections.Counter(r["kind"] for r in records)
    stub_docs = sum(1 for p in per_doc if len(p["clean"].split()) < STUB_WORDS)
    note_chunks = sum(r["is_note"] for r in records)
    repeal_chunks = sum(bool(r["repeal_sentences"]) for r in records)
    repeal_docs = len({r["doc_id"] for r in records if r["repeal_sentences"]})
    merged = sum(p["merged"] for p in per_doc)
    windows_added = sum(p["windows_added"] for p in per_doc)
    split_pieces = sum(1 for r in records if r["parts"] > 1 and r["part"] == 1)
    blocks = noise["blocks"]
    rejoined = sum(b["rejoined"] for _, _, b in blocks)
    docs_with_noise = len({doc_id for doc_id, _, _ in blocks})

    def cover(field):
        return f"{sum(p['meta'][field] is not None for p in per_doc) / len(per_doc):.0%}"

    rng = random.Random(SEED)
    noise_examples = rng.sample([b for b in blocks if b[2]["parts"]["running_title"]], 4) + \
        rng.sample([b for b in blocks if b[2]["rejoined"]], 1)
    sample = sorted(rng.sample(records, 15), key=lambda r: r["id"])
    shortest = min(records, key=lambda r: (r["words"], r["id"]))
    longest = max(records, key=lambda r: (r["words"], r["id"]))

    L = []
    add = L.append
    add("# Chunking report: labour law (Phase 1A)\n")
    add("How the 1,284 labour-law documents (volume 41, *ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ*) were cleaned and cut into chunks "
        "for search. This file is generated by [`scripts/build_chunks.py`](../scripts/build_chunks.py) from "
        "the real output in `data/processed/labour_chunks.jsonl`; every number and example below comes from "
        "that run. No AI, no embeddings, no database were used.\n")

    add("## At a glance\n")
    add("| | |\n|---|---|")
    add(f"| Documents | {n(len(docs))} |")
    add(f"| **Chunks** | **{n(len(records))}** (Phase 0 estimated about {n(PHASE0_ESTIMATE)}) |")
    add(f"| Words per chunk | median {statistics.median(words):.0f}, average {statistics.mean(words):.0f}, "
        f"shortest {min(words)}, longest {max(words)} |")
    add(f"| Chunking method | by article: {n(methods['article'])} documents; by numbered paragraph: "
        f"{n(methods['paragraph'])}; by size: {n(methods['size'])}; kept whole (short): {n(methods['whole'])} |")
    add(f"| Page noise removed | {n(norm_words - clean_words)} words out of {n(norm_words)} "
        f"({(norm_words - clean_words) / norm_words:.1%}), from {n(docs_with_noise)} documents |")
    add(f"| Article headings moved to their own article | {n(noise['headings']['headings_moved'])} |")
    add(f"| Stubs (document under {STUB_WORDS} words) | {n(stub_docs)} documents |")
    add(f"| Editorial notes | {n(note_chunks)} chunks |")
    add(f"| Repeal sentences kept | {n(repeal_chunks)} chunks in {n(repeal_docs)} documents |")
    add("")
    add(f"Why {n(len(records))} and not {n(PHASE0_ESTIMATE)}: the Phase 0 estimate had no overlap and no "
        "paragraph fallback. Here, long pieces are cut into windows that share about 50 words (so they need a "
        f"few more chunks), {n(methods['paragraph'])} documents without articles are split by numbered "
        "paragraph instead of being one big piece, and the article regex no longer counts references like "
        "\"Άρθρο 3 της οδηγίας\" as markers.\n")

    add("## What happens to each document\n")
    add("1. **Normalise** the characters (same module will clean user questions later).")
    add("2. **Remove printed-page noise**: page numbers, update-issue lines, book position codes and the "
        "running titles printed next to them.")
    add("3. **Read the header**: act type, number, year, ΦΕΚ and title.")
    add("4. **Cut into pieces**: by article if there are article markers, otherwise by numbered paragraph, "
        "otherwise by size. The header/preamble is its own piece. In the editors' style an article's heading "
        "comes *before* its marker (\"… οδηγεί η κλίμαξ. Φορηταί κλίμακες Άρθρ.17.-…\"), so after cutting, "
        "a heading left at the end of a piece is moved to the start of the next one.")
    add(f"5. **Tidy the pieces**: pieces under {MIN_WORDS} words join the previous one; pieces over "
        f"{MAX_WORDS} words are cut into windows of at most {MAX_WORDS} words, sharing about {OVERLAP} words "
        "with the next window, so a sentence on the border is never lost.")
    add("6. **Label each chunk** and build the *text to embed*: a short header "
        "(\"Ν. 2994/1922, Άρθρο 9, title…\") plus the chunk text.\n")

    add("## 1. Normalisation\n")
    add("| Step | Changes in volume 41 |\n|---|---:|")
    rows = [
        ("Micro sign `µ` → Greek `μ`", norm_counts["micro_sign"]),
        ("Spacing tonos + vowel → accented vowel (`΄Αρθρ.` → `Άρθρ.`)", norm_counts["spacing_tonos"]),
        ("Capital words split by a stray space joined (`ΕΡΓ ΑΣΙΑΣ` → `ΕΡΓΑΣΙΑΣ`)", norm_counts["split_caps_joined"]),
        ("Words with Latin look-alikes made Greek (`Aριθ` → `Αριθ`)", norm_counts["lookalike_words_to_greek"]),
        ("Latin words with Greek look-alikes made Latin (`ΚG` → `KG`, `ΙV` → `IV`)", norm_counts["lookalike_words_to_latin"]),
        ("Mixed-script words left alone (e.g. `μg`, a real unit)", norm_counts["mixed_words_left"]),
        ("Symbol-font characters mapped (formulas, tables)", norm_counts["symbol_font_chars"]),
        ("Symbol-font quote characters → `«»`", norm_counts["symbol_font_quotes"]),
        ("Other private-use characters dropped", norm_counts["private_use_dropped"]),
        ("Number glued to a word split (`-339Διεθνής` → `-339 Διεθνής`)", norm_counts["glued_numbers_split"]),
        ("Soft hyphens and other invisible characters removed", norm_counts["invisible_chars"]),
        ("No-break spaces → normal spaces", norm_counts["no_break_spaces"]),
        ("Documents changed by Unicode NFC", norm_counts["nfc_changed"]),
    ]
    for label, value in rows:
        add(f"| {label} | {n(value)} |")
    add("")
    add("Volume 41 is much cleaner than the full dataset: no Symbol-font quotes, soft hyphens or no-break "
        "spaces occur in it. Those steps are still in the module, tested with real examples from other "
        "volumes, because the same code will clean user questions and maybe other volumes later.\n")
    add("Examples from the labour texts (before → after):\n")
    for name, found in normalisation_examples(docs).items():
        for before, after in found:
            add(f"- *{name}*: `{before}` → `{after}`")
    add("")

    add("## 2. Printed-page noise\n")
    add("The texts come from a loose-leaf book, and its page headers ended up inside sentences. A header "
        "block mixes *anchors* with a fixed shape (always removed) and *running titles*, which are ordinary "
        "Greek words. Running titles are removed only when they are on a list learned from the data and touch "
        "an anchor; words that are not on the list are never removed.\n")
    p = noise["parts"]
    add("| Part of a header block | Removed |\n|---|---:|")
    add(f"| Replacement notes `(Αντί για τη σελ. 91(θ)`, `(Μετά τη σελ. …)` | {n(p['replacement_note'])} |")
    add(f"| Page numbers `Σελ. 228`, `Σελίς 307`, `Σελ. 30,207(α)` | {n(p['page'])} |")
    add(f"| Update issues `Τεύχος 1294-Σελ. 33` | {n(p['issue'])} |")
    add(f"| Book position codes `15.Λ.α.58`, `15.Γ .β.20` | {n(p['position_code'])} |")
    add(f"| Running titles | {n(p['running_title'])} |")
    add(f"| Bare page numbers next to them (`451`, `- 151`, `ΙΣΤ`) | {n(p['page_number'])} |")
    add(f"| **Header blocks in total** | **{n(len(blocks))}** in {n(docs_with_noise)} documents |")
    add(f"| Words removed | {n(norm_words - clean_words)} ({(norm_words - clean_words) / norm_words:.1%} of the text) |")
    add(f"| Words cut in two by a page break and joined again (`υπαλ` + `ληλικής`) | {n(rejoined)} |")
    add("")
    add(f"**The title list.** {len(titles)} running titles were learned from text that sits *between* two "
        "anchors and appears at least twice (so a stray sentence can't get in). The "
        f"{len(weak)} chapter and subject names that were not already on the list are used too, but more "
        "carefully: only when more header follows them. That rule exists because of a real case, a form "
        "whose heading \"Καταγγελία συμβάσεως εργασίας\" is also a chapter name. The full list is in "
        "`data/processed/running_titles.json`. Some learned titles:\n")
    for t in sorted(titles.values())[:12]:
        add(f"- {t}")
    add("")
    add("**Cross-references are kept.** Lowercase `σελ.` inside the text (\"ανωτ. σελ. 306,823\", \"τόμ. 2Α "
        "σελ. 354\") points to other pages of the book and stays.\n")
    leftovers = [(r["id"], m) for r in records for m in re.finditer(r"Σελ\.|Σελίς|Τεύχος", r["text"])]
    add(f"**What is left.** {len(leftovers)} places in the chunks still contain `Σελ.`, `Σελίς` or `Τεύχος`. "
        "They are listed here so you can judge them:\n")
    for rid, m in leftovers:
        add(f"- `{rid}`: `{snippet(m.string, m.start(), m.end(), 50)}`")
    add("")
    add("Before → after examples (random, seeded):\n")
    for doc_id, text, b in noise_examples:
        i = text.find(b["text"])
        before = snippet(text, i, i + len(b["text"]), 60)
        after_text = text[max(0, i - 60):i].rstrip() + ("" if b["rejoined"] else " ") + \
            text[i + len(b["text"]):i + len(b["text"]) + 60].lstrip()
        add(f"- Document {doc_id}:")
        add(f"  - before: `{before}`")
        add(f"  - after: `…{after_text.strip()}…`")
    add("")

    add("## 3. Chunks\n")
    add("| Method | Documents | Chunks |\n|---|---:|---:|")
    for m, label in [("article", "By article"), ("paragraph", "By numbered paragraph (no article markers)"),
                     ("size", "By size (no markers, no numbered paragraphs, long)"),
                     ("whole", "Kept whole (no markers, short)")]:
        add(f"| {label} | {n(methods[m])} | {n(chunks_by_method[m])} |")
    add(f"| **Total** | **{n(len(docs))}** | **{n(len(records))}** |")
    add("")
    add("| Kind of chunk | Chunks |\n|---|---:|")
    for k, label in [("preamble", "Header / preamble (\"Προοίμιο\")"), ("article", "Article"),
                     ("paragraph", "Numbered paragraph"), ("whole", "Whole short document"),
                     ("size", "Window of a long unstructured document")]:
        add(f"| {label} | {n(kinds[k])} |")
    add("")
    add(f"Pieces under {MIN_WORDS} words merged into a neighbour: {n(merged)}. Long pieces cut into windows: "
        f"{n(split_pieces)}, which added {n(windows_added)} chunks.\n")
    add("**Length (words per chunk):**\n")
    add("| Shortest | 10% | 25% | Median | Average | 75% | 90% | Longest |")
    add("|---:|---:|---:|---:|---:|---:|---:|---:|")
    add(f"| {min(words)} | {pct(words, 10)} | {pct(words, 25)} | {statistics.median(words):.0f} | "
        f"{statistics.mean(words):.0f} | {pct(words, 75)} | {pct(words, 90)} | {max(words)} |")
    add("")
    edges = [(1, 20), (20, 50), (50, 100), (100, 200), (200, 350), (350, 501)]
    add("| Words | Chunks |\n|---|---:|")
    for lo, hi in edges:
        add(f"| {lo}–{hi - 1} | {n(sum(lo <= w < hi for w in words))} |")
    add("")
    add(f"Chunks under {MIN_WORDS} words still exist when a whole document is that short (a stub has no "
        "neighbour to join).\n")

    add("## 4. Labels on each chunk\n")
    add("Each line of `labour_chunks.jsonl` is one chunk with these fields:\n")
    add("| Field | Meaning |\n|---|---|")
    for f, meaning in [
        ("id", "stable id `glc-<document>-<sequence>`, e.g. `glc-03244-002`"),
        ("doc_id, split", "document number (0-based, train → validation → test, as in Phase 0) and its split"),
        ("volume, chapter, subject", "the dataset labels (names)"),
        ("act_type, act_abbr, act_number, year, fek", "from the header, when found"),
        ("title", "title of the act, from the header"),
        ("citation", "how the chunk names its source: `Ν. 2994/1922`, or, without an act number, act type + «title» "
                     "+ (chapter, year)"),
        ("citation_fallback", "`true` when the second form was needed"),
        ("method, kind", "how the document was cut, and what this chunk is (preamble / article / …)"),
        ("article, article_numbers", "label like `Άρθρο 5` or `Άρθρα 13-19`, and the numbers as integers"),
        ("part, parts", "window number when a long piece was cut, e.g. 2 of 3"),
        ("words", "length of the chunk text"),
        ("is_stub", f"the whole document is under {STUB_WORDS} words"),
        ("is_note", "the chunk is mainly an editorial note, not law text: notes (brackets, or sentences starting "
                    "with e.g. `Κατηργήθη`, `Τροποποιηθείς`) cover at least half of it"),
        ("repeal_sentences", "the short sentence around each past-tense repeal verb, e.g. `Κατηργήθη δια του άρθρ. 12 "
                             "Α.Ν. 1836/1951 κατωτ. αριθ. 15.`, kept for later"),
        ("text", "the cleaned chunk text"),
        ("embed_text", "short header + newline + text; this is what will be embedded"),
    ]:
        add(f"| `{f}` | {meaning} |")
    add("")
    add("How often the header gave us each field (per document):\n")
    add("| Act type | Act number | Year | ΦΕΚ | Title |\n|---:|---:|---:|---:|---:|")
    add(f"| {cover('act_type')} | {cover('act_number')} | {cover('year')} | {cover('fek')} | {cover('title')} |")
    add("")
    add("Missing numbers are mostly real: many royal decrees and old laws have no number in the header "
        "(\"ΒΑΣΙΛΙΚΟΝ ΔΙΑΤΑΓΜΑ της 7/9 Φεβρ. 1951 …\"), and old acts have no ΦΕΚ reference.\n")

    add("## 5. Fifteen random chunks\n")
    add(f"Picked with a fixed seed ({SEED}), shown in full. `⏎` marks the newline between the header and the "
        "text in *text to embed*.\n")
    for r in sample:
        add(chunk_block(r))

    add("## 6. The five worst cases\n")
    add(chunk_block(shortest, "Shortest chunk"))
    add(f"Only {shortest['words']} words. It is a whole document with nothing to merge with.\n")
    add(chunk_block(longest, "Longest chunk"))
    add(f"{longest['words']} words, close to the {MAX_WORDS}-word limit by design.\n")
    for title, why, r in strangeness(records):
        add(chunk_block(r, title))
        add(why + "\n")

    write_fixes(add, noise["fixes"], records)

    add("## Known limits of this step\n")
    add("- Running titles that appear only once and are not chapter or subject names stay in the text. "
        "That is the safe side: a few extra words instead of lost law text.")
    add("- A word cut by a page break is joined only when the break sits right against it; a few such "
        "words may remain split.")
    add("- Article order inside a document is kept as found (often shuffled); use `article_numbers`.")
    add("- Tables, formulas and forms survive badly (see the worst cases); they are kept, not repaired.")
    add("- A title ends at the first full stop after a word of 5+ letters. Short abbreviations (\"Υπ.\", "
        "\"Εθν.\") don't end it, but a longer one (\"Κοινων.\") still can.")
    add("- A moved heading is recognised only as an unfinished phrase (no full stop) of at most 15 words "
        "at the end of a piece; a heading that contains an abbreviation with a full stop stays where it is.")
    add("- `is_note` recognises editorial sentences by how they start (a bracket or a verb such as "
        "\"Κατηργήθη\"). An editorial sentence that starts differently (\"Ο δια του ανωτέρω Β.Δ. … συσταθείς …\") "
        "doesn't count, so a few chunks that are mostly notes stay unflagged. That errs on the side of keeping "
        "law text visible.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    raw = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/raw/greek_legal_code")
    out_dir = ROOT / "data/processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs, normalized, norm_counts, titles, weak, noise, per_doc, records = run(raw)
    with open(out_dir / "labour_chunks.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "running_titles.json").write_text(
        json.dumps({"learned": sorted(titles.values()), "label_names": sorted(weak.values())},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(ROOT / "docs/chunking-report.md", docs, normalized, norm_counts, titles, weak, noise, per_doc,
                 records)
    print(f"{len(docs)} documents -> {len(records)} chunks; wrote {out_dir / 'labour_chunks.jsonl'} "
          f"and docs/chunking-report.md")


if __name__ == "__main__":
    main()
