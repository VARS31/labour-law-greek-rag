"""Phase 0 data exploration for the Hugging Face dataset AI-team-UoA/greek_legal_code.

Reads the 9 parquet files (3 label configs x 3 splits) and writes the numbers behind
docs/data-exploration.md. No embeddings, no database.

Usage:
    .venv/bin/python -I scripts/explore_data.py [RAW_DIR] [OUT_DIR]

Defaults: RAW_DIR=data/raw/greek_legal_code, OUT_DIR=data/exploration
"""

import collections
import json
import math
import re
import statistics
import sys
import unicodedata
from pathlib import Path

import duckdb

LEVELS = ["volume", "chapter", "subject"]
SPLITS = ["train", "validation", "test"]
LABOUR_VOLUME = 41  # ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ

# --- article markers ------------------------------------------------------------------------
# Capitalised "article" followed by a number, ordinal or roman numeral. Covers the editors'
# abbreviated style "Άρθρ.1.-", modern "Άρθρο 1", katharevousa "Άρθρον 1", single-article acts,
# and the broken variants found in the data (spacing tonos "΄Αρθρ", no accent, ALL CAPS, Latin "o").
# Lowercase "άρθρο" and "(Άρθρ. 5 ..." / "Άρθρ. 5 παρ. 2" / "του άρθρου" are references, not markers.
ORDINAL = (r"(?:μόνον?|πρώτον?|δεύτερον?|τρίτον?|τέταρτον?|πέμπτον?|έκτον?|έβδομον?|όγδοον?"
           r"|ένατον?|δέκατον?|[IVXΙΧ]{1,6}(?![\wά-ώ]))")
REFERENCE = (r"(?:παρ|της|του|των|τον|την|εδ|περ|και|έως|ως|μέχρι|ν\.|Ν\.|π\.δ|Π\.Δ|Ν\.Δ|Α\.Ν|Β\.Δ"
             r"|Κανονισμού|Οδηγίας|Συμβάσεως|Σύμβασης|ΚΠολΔ|ΑΚ|ΠΚ)")
ARTICLE = re.compile(
    r"(?<![\wά-ώ\(])(?<!\(\s)(?<!\b[Ττ]ο\s)(?<!\b[Ττ]ου\s)(?<!\b[Σσ]το\s)"
    r"(?P<tonos>΄\s?)?(?P<alpha>Ά|Α|A)(?P<stem>ρθρ|ΡΘΡ)(?P<suffix>ον|ο|o|ΟΝ|Ο)?(?P<dot>\.?)\s*"
    r"(?:(?P<num>\d+)\s?[α-ω]?(?:\s?δις|\s?τρις)?(?:\s?[-–]\s?\d+)?|(?P<word>" + ORDINAL + r"))"
    r"(?P<dash>\s?\.?\s?[-–])?"
    r"(?!\s?" + REFERENCE + r"[\s\.])")
SINGLE_ARTICLE = re.compile(r"(?:Μόνον?|ΜΟΝΟΝ?)\s+(?:άρθρον?|ΑΡΘΡΟΝ?)")


def article_markers(text):
    found = list(ARTICLE.finditer(text)) + list(SINGLE_ARTICLE.finditer(text))
    return sorted(found, key=lambda m: m.start())


def article_number(m):
    return int(m.group("num")) if m.re is ARTICLE and m.group("num") else None


def marker_style(m):
    """Coarse label for the article-marker table in the doc."""
    if m.re is SINGLE_ARTICLE:
        return "Μόνον άρθρον"
    g = m.groupdict()
    if g["word"] and g["word"].lower().startswith("μόνο"):
        core = "Άρθρο(ν) μόνο(ν)"
    elif g["word"] and g["word"][0] in "IVXΙΧ":
        core = "Άρθρο + roman numeral (Άρθρο ΙΙ)"
    elif g["word"]:
        core = "Άρθρο + ordinal word (Άρθρο πρώτο)"
    elif g["dot"] and not g["suffix"]:
        core = "Άρθρ.N.- (abbreviated, with dash)"
    elif g["suffix"] in ("ον", "ΟΝ"):
        core = "Άρθρον N"
    else:
        core = "Άρθρο N"
    return core


def marker_variant(m):
    if m.re is SINGLE_ARTICLE:
        return "normal"
    g = m.groupdict()
    if g["tonos"]:
        return "spacing tonos before capital (΄Αρθρ)"
    if g["stem"] == "ΡΘΡ":
        return "ALL CAPS (ΑΡΘΡΟ)"
    if g["alpha"] == "A" or g["suffix"] == "o":
        return "Latin letter inside (Άρθρo / Aρθρο)"
    if g["alpha"] == "Α":
        return "no accent (Αρθρο)"
    return "normal"


# --- chunk + storage estimate ---------------------------------------------------------------
MAX_WORDS = 500   # longer article segments get split into pieces of at most this many words
MIN_WORDS = 20    # shorter segments (e.g. "Άρθρ.13-19.-(Καταργήθηκαν)") are merged into a neighbour


def chunk_word_counts(text, max_words=MAX_WORDS, min_words=MIN_WORDS):
    """Words per chunk if we chunk by article: preamble + one chunk per article, tiny bits merged,
    long articles split. A document without markers is one segment."""
    cuts = [m.start() for m in article_markers(text)]
    bounds = [0, *cuts, len(text)]
    segments = [len(text[a:b].split()) for a, b in zip(bounds, bounds[1:])]
    merged, carry = [], 0
    for w in segments:
        if w < min_words:
            if merged:
                merged[-1] += w
            else:
                carry += w
        else:
            merged.append(w + carry)
            carry = 0
    if carry:
        merged.append(carry)
    chunks = []
    for w in merged:
        pieces = math.ceil(w / max_words)
        chunks += [w / pieces] * pieces
    return chunks


# Bytes per stored chunk in Postgres + pgvector (pgvector 0.8.6 headers in Postgres.app):
#   Vector struct = 4 B varlena + 2 B dim + 2 B unused + 4 B per dim; halfvec = 2 B per dim.
#   STORAGE = external, so the vector goes to the TOAST table uncompressed, in ~2 KB pieces
#   (~40 B overhead each).
VECTOR_F32 = 8 + 4 * 1024
VECTOR_F16 = 8 + 2 * 1024
TOAST_PIECE, TOAST_OVERHEAD = 1996, 40
# HNSW index: each element tuple holds the full vector plus a neighbour list (~0.2-0.3 KB for m=16)
# and must fit in one 8 KB page. 1024-d float32 (~4.4 KB/element) -> 1 element per page;
# halfvec (~2.3 KB) -> 3 per page. Estimate only - measure with pg_relation_size in Phase 1.
HNSW_F32 = 8192
HNSW_F16 = 8192 / 3
ROW_OVERHEAD = 150      # tuple header, line pointer, ids, article number, labels
DOC_ROW = 500           # one row per document: header/title + labels
SAFETY = 1.2            # free space in pages, fillfactor, small btree indexes
SUPABASE_FREE_MB = 500


def storage_mb(n_chunks, n_docs, text_bytes):
    def toasted(size):
        return size + math.ceil(size / TOAST_PIECE) * TOAST_OVERHEAD

    base = text_bytes + n_chunks * ROW_OVERHEAD + n_docs * DOC_ROW
    out = {}
    for name, vec, hnsw in [("float32", VECTOR_F32, HNSW_F32), ("halfvec", VECTOR_F16, HNSW_F16)]:
        parts = {
            "text": text_bytes,
            "vectors": n_chunks * toasted(vec),
            "hnsw_index": n_chunks * hnsw,
            "rows_and_docs": n_chunks * ROW_OVERHEAD + n_docs * DOC_ROW,
        }
        total = (base + parts["vectors"] + parts["hnsw_index"]) * SAFETY
        out[name] = {k: round(v / 1e6, 1) for k, v in parts.items()}
        out[name]["total_with_margin"] = round(total / 1e6, 1)
        out[name]["plus_fulltext_index"] = round((total + text_bytes * SAFETY) / 1e6, 1)
    return out


# --- helpers ----------------------------------------------------------------------------------
def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


def summary(values):
    return {"min": min(values), "p10": pct(values, 10), "p25": pct(values, 25),
            "median": statistics.median(values), "mean": round(statistics.mean(values)),
            "p75": pct(values, 75), "p90": pct(values, 90), "p95": pct(values, 95),
            "p99": pct(values, 99), "max": max(values), "total": sum(values)}


def load(raw):
    con = duckdb.connect()
    names, labels, texts = {}, {}, {}
    for level in LEVELS:
        meta = con.execute(f"select value from parquet_kv_metadata('{raw}/{level}/train.parquet') "
                           "where key = 'huggingface'").fetchall()[0][0]
        names[level] = json.loads(meta)["info"]["features"]["label"]["names"]
        for split in SPLITS:
            rows = con.execute(f"select text, label from read_parquet('{raw}/{level}/{split}.parquet')").fetchall()
            labels[level, split] = [r[1] for r in rows]
            texts[level, split] = [r[0] for r in rows]
    docs = []
    for split in SPLITS:
        # The three configs hold the same texts in the same order; only the label differs.
        assert texts["volume", split] == texts["chapter", split] == texts["subject", split]
        for i, text in enumerate(texts["volume", split]):
            docs.append({"id": len(docs), "split": split, "text": text, "words": len(text.split()),
                         **{level: labels[level, split][i] for level in LEVELS}})
    return names, docs


# --- sections -------------------------------------------------------------------------------
def hierarchy(names, docs):
    def parents(child, parent):
        p = collections.defaultdict(set)
        for d in docs:
            p[d[child]].add(d[parent])
        multi = {k: v for k, v in p.items() if len(v) > 1}
        return {"count": len(multi),
                "examples": [{"name": names[child][k], "parents": sorted(names[parent][x] for x in v)}
                             for k, v in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:6]]}

    def per(group, member):
        g = collections.defaultdict(set)
        for d in docs:
            g[d[group]].add(d[member] if member != "doc" else d["id"])
        n = [len(v) for v in g.values()]
        return {"min": min(n), "median": statistics.median(n), "max": max(n)}

    return {"docs": len(docs), "volumes": len(names["volume"]), "chapters": len(names["chapter"]),
            "subjects": len(names["subject"]),
            "splits": collections.Counter(d["split"] for d in docs),
            "chapters_per_volume": per("volume", "chapter"), "subjects_per_chapter": per("chapter", "subject"),
            "docs_per_subject": per("subject", "doc"), "docs_per_chapter": per("chapter", "doc"),
            "chapters_under_several_volumes": parents("chapter", "volume"),
            "subjects_under_several_chapters": parents("subject", "chapter")}


def length_buckets(docs):
    edges = [(0, 30), (30, 100), (100, 500), (500, 2000), (2000, 10000), (10000, math.inf)]
    return [{"words": f"{lo}-{hi}" if hi != math.inf else f"{lo}+",
             "docs": sum(lo <= d["words"] < hi for d in docs)} for lo, hi in edges]


def longest(names, docs, n=5):
    return [{"id": d["id"], "words": d["words"], "volume": names["volume"][d["volume"]], "start": d["text"][:120]}
            for d in sorted(docs, key=lambda d: -d["words"])[:n]]


def volumes(names, docs):
    out = []
    for v, name in enumerate(names["volume"]):
        ds = [d for d in docs if d["volume"] == v]
        out.append({"id": v, "name": name, "docs": len(ds), "words": sum(d["words"] for d in ds),
                    "chapters": len({d["chapter"] for d in ds}), "subjects": len({d["subject"] for d in ds})})
    return sorted(out, key=lambda r: -r["docs"])


MONTH = r"(?:Ιαν|Φεβ|Μαρ|Απρ|Μα[ΐϊιί]|Ιουν|Ιουλ|Αυγ|Σεπ|Οκτ|Νοε|Δεκ)[α-ωάέήίόύώϊΐ]*\.?"
YEAR = r"(18[2-9]\d|19\d\d|20[0-2]\d)"
HEADER_DATE = re.compile(
    rf"(?:της|την)\s+\d{{1,2}}(?:\s*{MONTH})?(?:\s*[/\-–]\s*\d{{1,2}})?\s*{MONTH}\s*(?:{YEAR}\s*)?"
    rf"(?:[/\-–]\s*\d{{1,2}}\s*{MONTH}\s*)?\.?\s*{YEAR}")


def header_year(text):
    """Year from the header date, e.g. "της 18/19 Μαρτ. 1968" -> 1968 (second date = publication)."""
    m = HEADER_DATE.search(text[:300])
    return int(m.group(2)) if m else None


def dates(docs):
    years = [y for d in docs if (y := header_year(d["text"]))]
    return {"docs_with_header_date": len(years), "share": round(len(years) / len(docs), 3),
            "min": min(years), "p5": pct(years, 5), "median": statistics.median(years),
            "p95": pct(years, 95), "max": max(years),
            "per_decade": dict(sorted(collections.Counter(y // 10 * 10 for y in years).items()))}


LEADING_NUMBER = re.compile(r"^\s*\d+\s?[α-ωΑ-Ωa-zA-Z]?\s?\.\s*")
ACT_TYPES = [
    ("Νόμος (law)", r"^(?:ΝΟΜΟΣ|ΝΟΜΟΙ)"),
    ("Αναγκαστικός νόμος (emergency law)", r"^ΑΝΑΓΚ"),
    ("Νομοθετικό διάταγμα (legislative decree)", r"^ΝΟΜΟΘ|^ΝΟΜ\.\s?ΔΙΑΤ"),
    ("Βασιλικό διάταγμα (royal decree)", r"^ΒΑΣΙΛ|^Β\.\s?Δ"),
    ("Προεδρικό διάταγμα (presidential decree)", r"^ΠΡΟΕΔΡ|^Π\.\s?Δ"),
    ("Υπουργική απόφαση (ministerial decision)", r"^(?:ΚΟΙΝΗ\s)?[ΑA]ΠΟΦ"),  # Latin "A" occurs too
    ("Πράξη, mostly of the cabinet (act)", r"^ΠΡ\s?ΑΞ"),
    ("Διεθνής σύμβαση (international convention)", r"^(?:ΔΙΕΘΝΗΣ\s)?ΣΥΜΒΑΣ"),
]


def act_types(docs):
    c = collections.Counter()
    for d in docs:
        m = LEADING_NUMBER.match(d["text"])
        head = d["text"][m.end():].lstrip() if m else ""
        kind = "no numbered header" if not m else next(
            (label for label, pat in ACT_TYPES if re.match(pat, head)), "other")
        c[kind] += 1
    return c.most_common()


def articles(docs):
    styles, variants, styles_docs = collections.Counter(), collections.Counter(), collections.Counter()
    per_doc, backwards, tail_moved, restarts, numbered = collections.Counter(), 0, 0, 0, 0
    for d in docs:
        ms = article_markers(d["text"])
        n = len(ms)
        per_doc["0" if n == 0 else "1" if n == 1 else "2-5" if n <= 5 else "6-20" if n <= 20
                else "21-100" if n <= 100 else ">100"] += 1
        for s in {marker_style(m) for m in ms}:
            styles_docs[s] += 1
        styles.update(marker_style(m) for m in ms)
        variants.update(marker_variant(m) for m in ms)
        nums = [x for x in map(article_number, ms) if x is not None]
        if len(nums) >= 3:
            numbered += 1
            backwards += any(b < a for a, b in zip(nums, nums[1:]))
            tail_moved += nums[0] == 1 and nums[1] > 2 and 2 in nums[2:]
            restarts += nums.count(1) >= 2
    return {"markers_total": sum(styles.values()), "styles": styles.most_common(),
            "styles_docs": styles_docs.most_common(), "variants": variants.most_common(),
            "markers_per_doc": per_doc, "docs_with_3plus_numbered": numbered,
            "numbers_go_backwards": backwards, "pattern_1_then_last_then_2": tail_moved,
            "article_1_twice_or_more": restarts}


GREEK = "Ͱ-Ͽἀ-῿"


def quality(docs):
    texts = [d["text"] for d in docs]

    def docs_with(pattern):
        r = re.compile(pattern)
        return sum(bool(r.search(t)) for t in texts)

    def occurrences(pattern):
        r = re.compile(pattern)
        return sum(len(r.findall(t)) for t in texts)

    mixed, mixed_docs = collections.Counter(), 0
    for t in texts:
        found = [w for w in re.findall(r"\w+", t) if re.search(f"[{GREEK}]", w) and re.search("[A-Za-z]", w)]
        mixed.update(found)
        mixed_docs += bool(found)

    def dedup_key(t, head_only=False):
        t = LEADING_NUMBER.sub("", t)
        t = unicodedata.normalize("NFD", t.lower())
        t = re.sub(r"[\W_]+", " ", "".join(ch for ch in t if not unicodedata.combining(ch))).strip()
        return t[:300] if head_only else t

    dup = {}
    for name, head_only in [("same_text_ignoring_leading_number", False), ("same_first_300_chars", True)]:
        groups = collections.defaultdict(list)
        for d in docs:
            groups[dedup_key(d["text"], head_only)].append(d)
        multi = [g for g in groups.values() if len(g) > 1]
        dup[name] = {"groups": len(multi), "extra_copies": sum(len(g) - 1 for g in multi),
                     "groups_across_splits": sum(len({d["split"] for d in g}) > 1 for g in multi),
                     "groups_with_different_volume": sum(len({d["volume"] for d in g}) > 1 for g in multi)}

    no_header = [d for d in docs if not LEADING_NUMBER.match(d["text"])]
    starts_with_article = sum(bool((ms := article_markers(d["text"])) and ms[0].start() < 5) for d in no_header)
    return {
        "docs_with_newline": sum("\n" in t for t in texts),
        "replacement_char_docs": docs_with("�"),
        "micro_sign_instead_of_mu": {"occurrences": occurrences("µ"), "docs": docs_with("µ")},
        "private_use_glyphs": {"occurrences": occurrences("[-]"), "docs": docs_with("[-]")},
        "cyrillic": {"occurrences": occurrences("[Ѐ-ӿ]"), "docs": docs_with("[Ѐ-ӿ]")},
        "soft_hyphen_or_nbsp_docs": docs_with("[­ ]"),
        "latin_letters_inside_greek_words": {"occurrences": sum(mixed.values()), "distinct": len(mixed),
                                             "docs": mixed_docs, "top": mixed.most_common(12)},
        "polytonic_chars": occurrences("[ἀ-῿]"),
        "docs_changed_by_nfc": sum(unicodedata.normalize("NFC", t) != t for t in texts),
        "spacing_tonos_before_vowel": {"occurrences": occurrences(r"(?:^|\s)΄[ΑΕΗΙΟΥΩαεηιουω]"),
                                       "docs": docs_with(r"(?:^|\s)΄[ΑΕΗΙΟΥΩαεηιουω]")},
        "article_word_forms": {w: sum(t.count(w) for t in texts)
                               for w in ["Άρθρο", "Αρθρο", "ΑΡΘΡΟ", "Άρθρον", "Αρθρον", "Άρθρ.", "Αρθρ.", "΄Αρθρ"]},
        "page_headers_Σελ": docs_with(r"Σελ(?:\.|ίς)\s?\d"),
        "page_headers_Τεύχος": docs_with(r"Τεύχος\s"),
        "classification_codes": docs_with(r"\b\d{1,2}\.[Α-Ω][α-ω]?\.[α-ω]{1,2}\.\d"),
        "editorial_notes": docs_with(r"\((?:Κατ[αη]ργ|Τροποπ|Αντικ|Περιελ|Παραλ)"),
        "form_placeholders_ellipsis": docs_with("……"),
        "no_numbered_header": len(no_header),
        "no_header_starts_with_article": starts_with_article,
        "stubs": {f"under_{k}_words": sum(d["words"] < k for d in docs) for k in (10, 20, 30, 50)},
        "duplicates": dup,
    }


def corpus_estimate(names, docs):
    chunk_words = [w for d in docs for w in chunk_word_counts(d["text"])]
    n_chunks = len(chunk_words)
    text_bytes = sum(len(d["text"].encode("utf-8")) for d in docs)
    sensitivity = {mw: sum(len(chunk_word_counts(d["text"], max_words=mw)) for d in docs) for mw in (300, 800)}
    return {
        "docs": len(docs), "words": sum(d["words"] for d in docs),
        "docs_with_articles": sum(bool(article_markers(d["text"])) for d in docs),
        "article_markers": sum(len(article_markers(d["text"])) for d in docs),
        "chunks": n_chunks, "chunks_if_max_words": sensitivity,
        "words_per_chunk": {"median": round(statistics.median(chunk_words)), "mean": round(statistics.mean(chunk_words))},
        "text_mb": round(text_bytes / 1e6, 1),
        "years": (lambda ys: {"min": min(ys), "median": statistics.median(ys), "max": max(ys)} if ys else None)(
            [y for d in docs if (y := header_year(d["text"]))]),
        "storage_mb": storage_mb(n_chunks, len(docs), text_bytes),
    }


def labour(names, docs):
    ds = [d for d in docs if d["volume"] == LABOUR_VOLUME]
    chapters = collections.Counter(names["chapter"][d["chapter"]] for d in ds)
    return {"volume": names["volume"][LABOUR_VOLUME], **corpus_estimate(names, ds),
            "words_per_doc": summary([d["words"] for d in ds]), "longest": longest(names, ds, 3),
            "chapters": chapters.most_common()}


def samples(docs, words_summary, out):
    """One short, one typical and one long labour-law document, picked by dataset-wide length."""
    pool = [d for d in docs if d["volume"] == LABOUR_VOLUME and LEADING_NUMBER.match(d["text"])]
    picks = {}
    for name, target, need_articles in [("short", words_summary["p10"], 0),
                                        ("typical", words_summary["median"], 0),
                                        ("long", words_summary["p90"], 3)]:
        cands = [d for d in pool if len(article_markers(d["text"])) >= need_articles]
        best = min(cands, key=lambda d: (abs(d["words"] - target), d["id"]))
        picks[name] = {"id": best["id"], "split": best["split"], "words": best["words"], "target": target}
        (out / f"sample_{name}.txt").write_text(best["text"], encoding="utf-8")
    return picks


def main():
    raw = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/greek_legal_code")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "data/exploration")
    out.mkdir(parents=True, exist_ok=True)

    names, docs = load(raw)
    words = summary([d["words"] for d in docs])
    stats = {
        "hierarchy": hierarchy(names, docs),
        "volumes": volumes(names, docs),
        "words_per_doc": words,
        "length_buckets": length_buckets(docs),
        "longest": longest(names, docs),
        "dates": dates(docs),
        "act_types": act_types(docs),
        "articles": articles(docs),
        "quality": quality(docs),
        "labour": labour(names, docs),
        "full": corpus_estimate(names, docs),
        "samples": samples(docs, words, out),
        "assumptions": {"max_words": MAX_WORDS, "min_words": MIN_WORDS, "vector_f32_bytes": VECTOR_F32,
                        "vector_f16_bytes": VECTOR_F16, "hnsw_f32_bytes": HNSW_F32, "hnsw_f16_bytes": HNSW_F16,
                        "row_overhead": ROW_OVERHEAD, "doc_row": DOC_ROW, "safety": SAFETY,
                        "supabase_free_mb": SUPABASE_FREE_MB},
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "volumes"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
