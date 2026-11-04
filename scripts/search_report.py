"""Phase 1B measurements: database size, search speed without and with an HNSW index, eight example
questions with the three result lists, and near-duplicate chunks. Writes docs/search-report.md.

Needs the database (docker compose up -d) loaded with `python -m labour_rag.load`, and Ollama running.

Usage:
    .venv/bin/python scripts/search_report.py
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labour_rag import search  # noqa: E402
from labour_rag.db import HNSW_EF_SEARCH, apply_schema, connect  # noqa: E402
from labour_rag.model_client import ModelClient  # noqa: E402
from labour_rag.normalize import normalize  # noqa: E402
from labour_rag.retrieve import NEAR_IDENTICAL, overlap, word_set  # noqa: E402

REPORT = ROOT / "docs/search-report.md"
RUNS = 7                  # timing runs per query; the median is reported
PHASE0 = {"chunks": 5301, "text": 9.7, "vectors": 22.4, "hnsw": 43.4, "rows": 1.4, "total": 92.3, "no_hnsw": 40.2}

# Questions a person would realistically type, in everyday modern Greek. The texts are mostly katharevousa.
QUESTIONS = [
    ("Πόσες ημέρες κανονική άδεια με αποδοχές δικαιούται ο μισθωτός;", "annual leave"),
    ("Ποιες είναι οι ώρες λειτουργίας των καταστημάτων και οι ώρες εργασίας του προσωπικού τους;",
     "working hours in shops"),
    ("Τι αποζημίωση δικαιούται ο ιδιωτικός υπάλληλος όταν απολύεται;", "dismissal compensation"),
    ("Πώς αμείβεται η υπερωριακή εργασία;", "overtime"),
    ("Από ποια ηλικία επιτρέπεται να εργάζονται οι ανήλικοι;", "work of minors"),
    ("Μέτρα υγιεινής και ασφάλειας για τους εργαζόμενους στις οικοδομές", "health and safety on construction sites"),
    ("Πώς υπολογίζεται το δώρο Χριστουγέννων των μισθωτών;", "Christmas bonus"),
    ("Τι προστασία έχει η εργαζόμενη μητέρα στην εγκυμοσύνη και μετά τον τοκετό;", "maternity protection"),
]

# Written by hand after reading the result lists of this run (exact search, which doesn't change between runs).
# Re-check them if the chunks, the model or the search code change.
COMMENTS = {
    1: "Hybrid did best. Semantic search put the key rule first, Α.Ν. 539/1945 Άρθρο 2 (\"Κάθε μισθωτός, μετά "
       "από συνεχή απασχόληση τουλάχιστο δώδεκα μηνών …\"), and also found the later decisions that raised the "
       "number of days (Υ.Α. 11400/1975, Υ.Α. 11282/1979, Π.Δ. 88/1999), even though they say \"άδεια μετ’ "
       "αποδοχών\" rather than \"κανονική άδεια\". Keyword search found five articles of Α.Ν. 539/1945 but put a "
       "salary-indexation act and a decree on cinema staff above its main article. Hybrid has Α.Ν. 539/1945 "
       "Άρθρο 2 and 5 at the top, then the related decisions and the ILO holidays convention (Ν. 2081/1952); one "
       "keyword leftover (the indexation act) sits at rank 3.",
    2: "Keyword and hybrid did best here, because the question repeats the title of the main law almost word for "
       "word: Ν.Δ. 1037/1971 «Περί χρονικών ορίων λειτουργίας καταστημάτων και εργασίας του προσωπικού αυτών». "
       "Keyword search put its preamble first and filled six places with its articles; hybrid kept seven. "
       "Semantic search reached that law only at rank 3 (Άρθρο 9, working time of shop staff) and otherwise "
       "returned later decisions that set opening hours for particular areas and trades: useful, but more "
       "specific. The other side of keyword's win: one law fills most of the list.",
    3: "Semantic did best. It returned Ν. 2112/1920, the classic law on dismissing private employees (Άρθρο 3 and "
       "6), and Ν. 3198/1955 on the amount of compensation, with little noise. Keyword search was misled by "
       "\"αποζημίωση\", which in these texts also means compensation for work accidents and travel allowances, "
       "and by \"υπάλληλος\", which also means civil servant: only 3 of its 10 results are on topic. Hybrid kept "
       "the main laws at the top but took over some of that noise further down (7 of 10 on topic).",
    4: "Semantic did best: all ten results are about overtime or working beyond the limits, led by Π.Δ. 119/1973 "
       "Άρθρο 5 (\"Υπερωρίαι\") and two decisions with the heading \"Αμοιβή υπερεργασίας\". Keyword search matched "
       "\"αμείβεται\" and \"εργασία\" too loosely and brought in bakery hours, young workers and the Christmas "
       "bonus. Hybrid kept the best semantic result first but let the Christmas bonus in at rank 3.",
    5: "Hybrid did best, with semantic close. Semantic search found the age rules old and new: the 1912 law on "
       "the work of women and minors (limits of 14 and 16 years), Ν. 1837/1989 on the protection of minors and an "
       "ILO convention on minimum age. Keyword search found mostly Ν. 1837/1989 and Π.Δ. 62/1998 on young "
       "workers, but also shipyard and tank-cleaning rules that only share the word \"ηλικία\". Hybrid puts "
       "Ν. 1837/1989 Άρθρο 3 first (when minors may work with a permit from the Labour Inspectorate) and keeps "
       "the old age-limit articles.",
    6: "No method did well, and the reason is vocabulary. Volume 41 does contain the right act, Π.Δ. 305/1996 on "
       "safety at «προσωρινά ή κινητά εργοτάξια», but it says \"εργοτάξια\" where the question says "
       "\"οικοδομές\". Semantic search ranks it 76th and keyword search not at all; all three return general "
       "health-and-safety decrees (factories, workplaces, shipyards) instead. Asked with the law's own word "
       "(\"Μέτρα ασφάλειας και υγείας στα εργοτάξια οικοδομών\"), semantic search puts it 1st and keyword 2nd. "
       "Two more lessons: in this dataset Π.Δ. 305/1996 is only a 32-word header, so even when found it can't "
       "answer the question; and the main older decree on building sites, Π.Δ. 1073/1981, is in another volume "
       "(Public works). This is exactly the case the Phase 3 rewriter is for.",
    7: "Semantic did best. It returned the standing decision on the Christmas and Easter bonuses, Κ.Υ.Α. "
       "19040/1981, with Άρθρο 3 (\"υπολογίζονται βάσει των πράγματι καταβαλλομένων αποδοχών\") near the top. "
       "Keyword search returned ten yearly decisions from 1964–1978, each granting that year's bonus in almost the "
       "same words: eight of them repeat an earlier one. Hybrid mixed the two and still has three repeats.",
    8: "Semantic did best: Π.Δ. 176/1997 on pregnant and breastfeeding workers (definitions, banned exposures, "
       "Άρθρο 8 \"Άδεια μητρότητας\"), an ILO maternity convention (Ν. 2274/1920) and Υ.Α. 11770/1984 on the length "
       "of maternity leave. Keyword search found Π.Δ. 176/1997 too, then drifted to general rules on \"προστασία "
       "των εργαζομένων\" (asbestos, noise, other risks). Hybrid kept the 176/1997 articles first but let some of "
       "that drift in, and pushed maternity leave (Άρθρο 8) down to rank 8.",
}
VERDICT = ("semantic on 5 questions, hybrid on 2, keyword (with hybrid) on 1; none found the construction-site act "
           "with the everyday word")
OVERALL = (
    "Semantic search is the strongest single method on these questions. It bridges everyday modern Greek and the "
    "katharevousa of the laws, and it isn't fooled by words with two meanings. Keyword search wins when the "
    "question repeats the words of a law's title, and fails on synonyms and ambiguous words. Hybrid with equal "
    "weights is the safest default for the Phase 1C baseline: it was never the worst of the three, and it had the "
    "main law at rank 1 in seven of the eight questions. But it also imports keyword noise, so a lower weight for "
    "the keyword list is worth testing on the Phase 2 evaluation set. No method fixes a vocabulary gap like "
    "\"οικοδομές\" versus \"εργοτάξια\"; that is a job for the Phase 3 rewriter. Near-identical chunks can fill "
    "the top 10 (see below), so the answer step will need to group repeats.")
PROBE_COMMENT = (
    "Yes, near-identical chunks crowd the top 10 when a question touches standard clauses. For the convention "
    "question, all ten semantic results are the denunciation clause of ten different conventions, and the "
    "word-overlap test counts seven of them as repeats; hybrid has eight. On the eight ordinary questions it "
    "happens much less, two repeats at most, except the Christmas bonus, where keyword search returned eight "
    "copies of the yearly decision. For Phase 1C this means grouping repeats (for example keeping one chunk per "
    "near-identical group, preferring the newest act) before choosing which chunks to give the model.")


def esc(text):
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def ms(seconds):
    return f"{seconds * 1000:.1f} ms"


def timed(fn, runs=RUNS):
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - started)
    return statistics.median(times), result


def plan_nodes(conn, vector):
    return " → ".join(search.explain_semantic(conn, vector))


def compact(settings_conn_factory=connect):
    """VACUUM FULL: rewrite the table without the dead row versions that reloads leave behind, so the sizes
    measure the data, not the history. Needs its own connection outside a transaction."""
    with settings_conn_factory(autocommit=True) as conn:
        conn.execute("VACUUM (FULL, ANALYZE) chunks")


def sizes(conn):
    q = conn.execute("""
        SELECT pg_database_size(current_database()), pg_total_relation_size('chunks'), pg_relation_size('chunks'),
               pg_relation_size(c.reltoastrelid) + coalesce(pg_indexes_size(c.reltoastrelid), 0),
               pg_indexes_size('chunks')
        FROM pg_class c WHERE c.relname = 'chunks'""").fetchone()
    cols = conn.execute("""SELECT sum(pg_column_size(text)), sum(pg_column_size(embed_text)),
                                  sum(pg_column_size(embedding)), sum(pg_column_size(fts)), count(*),
                                  sum(octet_length(text)), sum(octet_length(embed_text))
                           FROM chunks""").fetchone()
    indexes = conn.execute("""SELECT indexrelname, pg_relation_size(indexrelid) FROM pg_stat_user_indexes
                              WHERE relname = 'chunks' ORDER BY 1""").fetchall()
    return {"database": q[0], "table_total": q[1], "heap": q[2], "toast": q[3], "indexes": q[4],
            "text": cols[0], "embed_text": cols[1], "embedding": cols[2], "fts": cols[3], "rows": cols[4],
            "text_raw": cols[5], "embed_text_raw": cols[6], "index_sizes": dict(indexes)}


IDENTICAL = 0.8         # stricter level for the whole-collection count
# A ninth question, only for the near-duplicate check: it asks about the standard ILO convention clauses.
PROBE = "Πότε τίθεται σε ισχύ μια διεθνής σύμβαση εργασίας και πώς μπορεί να καταγγελθεί;"


def near_duplicates(results):
    """Results whose wording is near-identical to a higher-ranked result in the same list."""
    seen, dups = [], []
    for r in results:
        s = word_set(r["text"])
        match = next((p for p, ps in seen if overlap(s, ps) >= NEAR_IDENTICAL), None)
        if match:
            dups.append((r, match))
        seen.append((r, s))
    return dups


def corpus_twins(conn, neighbours=5):
    """Chunks with a near-identical twin: candidates are each chunk's 5 nearest embeddings (HNSW index), and a
    candidate counts when the wording overlaps by NEAR_IDENTICAL or more."""
    texts = dict(conn.execute("SELECT id, text FROM chunks").fetchall())
    titles = dict(conn.execute("SELECT id, coalesce(title, '') FROM chunks").fetchall())
    conn.execute("SET enable_seqscan = off")
    pairs = conn.execute(f"""
        SELECT c.id, n.id FROM chunks c CROSS JOIN LATERAL (
            SELECT d.id FROM chunks d WHERE d.id <> c.id
            ORDER BY d.embedding <=> c.embedding LIMIT {neighbours}) n""").fetchall()
    conn.execute("RESET enable_seqscan")
    sets = {i: word_set(t) for i, t in texts.items()}
    twins = {}
    for a, b in pairs:
        o = overlap(sets[a], sets[b])
        if o >= NEAR_IDENTICAL and o > twins.get(a, (None, 0))[1]:
            twins[a] = (b, o)
    convention = sum(1 for a in twins if re.search(r"[Σσ]υμβάσ|[Σσ]ύμβασ", titles[a]))
    yearly = sum(1 for a in twins if re.search(r"Δώρου|δώρου|επιδόματος", titles[a]))
    return {"chunks": len(texts), "with_twin": len(twins), "convention": convention, "bonus": yearly,
            "identical": sum(1 for _, o in twins.values() if o >= IDENTICAL),
            "examples": sorted(((a, b, o) for a, (b, o) in twins.items()), key=lambda t: -t[2])[:6]}


def measure():
    client = ModelClient.from_settings()
    out = {"questions": []}
    with connect() as conn:
        conn.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw")
        conn.commit()
        compact()
        out["sizes_without_hnsw"] = sizes(conn)
        out["embedding_stats"] = json.loads((ROOT / "data/processed/embedding_stats.json").read_text())

        client.embed(["προθέρμανση"])                                  # load the model once
        for question, topic in QUESTIONS:
            embed_time, vectors = timed(lambda: client.embed([normalize(question)]), 3)
            v = vectors[0]
            entry = {"question": question, "topic": topic, "embed": embed_time, "vector": v,
                     "lexemes": search.query_lexemes(conn, question)}
            for name, fn in [("semantic", lambda: search.semantic(conn, client, question, 10, v)),
                             ("keyword", lambda: search.keyword(conn, question, 10)),
                             ("hybrid", lambda: search.hybrid(conn, client, question, 10, vector=v))]:
                fn()                                                    # warm-up
                entry[f"{name}_time"], entry[name] = timed(fn)
            out["questions"].append(entry)
        out["probe"] = search.search_all(conn, client, PROBE, 10)
        out["plan_without"] = plan_nodes(conn, out["questions"][0]["vector"])

        started = time.perf_counter()
        apply_schema(conn)                                              # runs sql/004_hnsw_index.sql too
        conn.execute("ANALYZE chunks")
        conn.commit()
        out["hnsw_build"] = time.perf_counter() - started
        out["plan_with"] = plan_nodes(conn, out["questions"][0]["vector"])
        out["sizes_with_hnsw"] = sizes(conn)
        for entry in out["questions"]:
            v, question = entry["vector"], entry["question"]
            for name, fn in [("semantic", lambda: search.semantic(conn, client, question, 10, v)),
                             ("hybrid", lambda: search.hybrid(conn, client, question, 10, vector=v))]:
                fn()
                entry[f"{name}_time_hnsw"], entry[f"{name}_hnsw"] = timed(fn)
        out["twins"] = corpus_twins(conn)
    return out


def result_table(entry):
    lines = ["| # | Semantic | Keyword | Hybrid (RRF) |", "|---:|---|---|---|"]
    for i in range(10):
        cells = []
        for name in ("semantic", "keyword", "hybrid"):
            rows = entry[name]
            if i >= len(rows):
                cells.append("")
                continue
            r = rows[i]
            fl = search.flags(r)
            extra = ""
            if name == "hybrid":
                extra = f" (sem {r['semantic_rank'] or '–'}, kw {r['keyword_rank'] or '–'})"
            cells.append(f"`{r['id']}` · {r['score']:.3f}{extra}<br>{esc(r['citation'])}<br>"
                         f"*{esc(r['article'] or '-')}*{'' if fl == '-' else ' · ' + fl}<br>{esc(r['text'][:100])}…")
        lines.append(f"| {i + 1} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write(out):
    qs = out["questions"]
    s0, s1 = out["sizes_without_hnsw"], out["sizes_with_hnsw"]
    mb = lambda b: f"{b / 1e6:.1f} MB"   # noqa: E731
    es = out["embedding_stats"]
    hnsw_size = s1["index_sizes"].get("chunks_embedding_hnsw", 0)

    L = []
    add = L.append
    add("# Search report: database, embeddings and search (Phase 1B)\n")
    add("How the 5,740 labour-law chunks were stored in Postgres + pgvector, embedded with a local model and "
        "searched three ways. This file is generated by [`scripts/search_report.py`](../scripts/search_report.py) "
        "from measurements on this machine (Apple M5, Docker Desktop); the short comments under each question "
        "were written by hand after reading the results.\n")

    add("## At a glance\n")
    add("| | |\n|---|---|")
    add(f"| Chunks in the database | {s1['rows']:,} |")
    add(f"| Embedding model | `{es['model']}` via Ollama, 1024 numbers per chunk |")
    add(f"| Embedding time | {es['embedding_seconds'] / 60:.1f} minutes for {es['embedded']:,} chunks "
        f"({es['chunks_per_second']} chunks per second, {es['tokens']:,} tokens) |")
    add(f"| Database size | {mb(s1['database'])} in total, of which the chunks table {mb(s1['table_total'])} "
        f"(Phase 0 estimated about {PHASE0['total']:.0f} MB) |")
    sem0 = statistics.median(e["semantic_time"] for e in qs)
    sem1 = statistics.median(e["semantic_time_hnsw"] for e in qs)
    add(f"| Semantic search, database part | {ms(sem0)} without an index, {ms(sem1)} with HNSW |")
    add(f"| Keyword search | {ms(statistics.median(e['keyword_time'] for e in qs))} |")
    add(f"| Embedding the question | {ms(statistics.median(e['embed'] for e in qs))} (the slowest step) |")
    if VERDICT:
        add(f"| Best method on the 8 questions | {VERDICT} |")
    add("")

    add("## How it is set up\n")
    add("- **Database:** Postgres 17 with pgvector 0.8.6 in Docker (`docker-compose.yml`), on port 5433 because "
        "Postgres.app already uses 5432. The data lives in a named Docker volume, so it survives restarts.")
    add("- **Schema:** `sql/001_extensions.sql` (pgvector, unaccent), `sql/002_text_search.sql` (the Greek "
        "full-text configuration), `sql/003_chunks.sql` (the table, every column commented), "
        "`sql/004_hnsw_index.sql` (the vector index, added after the first measurements).")
    add("- **Embeddings:** `embed_text` (the short source header plus the chunk text) is embedded with "
        f"`{es['model']}` through Ollama. All model calls go through `labour_rag/model_client.py`; the model name "
        "comes from `.env`.")
    add("- **Loading:** `python -m labour_rag.load` upserts every chunk by id and embeds only new or changed "
        "chunks (it stores a hash of `embed_text` and the model name), so running it again adds no duplicates and "
        "costs nothing.")
    stopwords = len((ROOT / "sql/greek_labour.stop").read_text(encoding="utf-8").split())
    add("- **Keyword search:** Postgres full-text search with the configuration `greek_labour`: accents removed "
        f"(`unaccent`), Greek stemming, and a stopword list of {stopwords} words (`sql/greek_labour.stop`). Postgres' own "
        "Greek configuration has no stopwords, so without the list words like \"άρθρο\" (in 68% of the chunks), "
        "\"και\" and \"περί\" would match almost everything. Any query word may match (OR); results are ranked "
        "by `ts_rank`, shortened for long chunks.")
    add("- **Semantic search:** cosine similarity between the question's embedding and each chunk's.")
    add("- **Hybrid search:** Reciprocal Rank Fusion. Each method gives its top 50; a chunk scores "
        "1 / (60 + rank) in each list it appears in, and the scores are added.")
    add("- The question is cleaned with the same normalisation as the chunks before searching.\n")

    add("## Database size\n")
    add("Real sizes, measured with Postgres' own size functions, next to the Phase 0 estimate. Phase 0 assumed "
        f"{PHASE0['chunks']:,} chunks; there are {s1['rows']:,}.\n")
    add("| Part | Phase 0 estimate | Real |\n|---|---:|---:|")
    add(f"| Chunk text (`text`) | {PHASE0['text']} MB | {mb(s1['text'])} |")
    add(f"| Text to embed (`embed_text`, not in the estimate) | – | {mb(s1['embed_text'])} |")
    add(f"| Vectors | {PHASE0['vectors']} MB | {mb(s1['embedding'])} |")
    add(f"| Full-text column `fts` (not in the estimate) | – | {mb(s1['fts'])} |")
    for name, size in sorted(s1["index_sizes"].items()):
        est = f"{PHASE0['hnsw']} MB" if name == "chunks_embedding_hnsw" else "–"
        add(f"| Index `{name}` | {est} | {mb(size)} |")
    add(f"| **Chunks table with all indexes** | **{PHASE0['total']} MB** (with 20% margin) | **{mb(s1['table_total'])}** |")
    add(f"| Same, before the HNSW index | {PHASE0['no_hnsw']} MB | {mb(s0['table_total'])} |")
    add(f"| Whole database (including Postgres' own catalog) | – | {mb(s1['database'])} |")
    add("")
    raw = s1["text_raw"] + s1["embed_text_raw"]
    stored = s1["text"] + s1["embed_text"]
    add(f"- **Text:** the two text columns hold {mb(raw)} of UTF-8 text and take {mb(stored)} on disk "
        f"({'Postgres compresses long values' if stored < raw else 'no compression gain'}). The chunk text is stored "
        "twice (`text` and `embed_text`), which the Phase 0 estimate didn't count.")
    add(f"- **Vectors:** {s1['embedding'] / s1['rows']:,.0f} bytes per chunk (4 bytes × 1024 numbers + 8 bytes "
        "header), stored uncompressed, as estimated.")
    add(f"- **HNSW index:** {hnsw_size / s1['rows']:,.0f} bytes per chunk; Phase 0 assumed about 8,192 (one entry "
        f"per 8 KB page). Real size {mb(hnsw_size)} against an estimate of {PHASE0['hnsw']} MB for "
        f"{PHASE0['chunks']:,} chunks.")
    add("- Sizes are measured after `VACUUM FULL`, which rewrites the table without the dead row versions that "
        "updates leave behind. (Before that, a second load that rewrote every row had made the table about a "
        "third bigger.)")
    add(f"- **Total:** the chunks table with every index is {mb(s1['table_total'])}, "
        f"{'below' if s1['table_total'] / 1e6 < PHASE0['total'] else 'above'} the Phase 0 estimate of "
        f"{PHASE0['total']} MB and {s1['database'] / 5e6:.0f}% of the Supabase free plan's 500 MB "
        "(whole database).\n")

    add("## Search speed\n")
    add(f"Median of {RUNS} runs per question, on the 8 questions below. *Database part* is the time Postgres "
        "takes once the question's embedding is ready; embedding the question with Ollama comes on top for "
        "semantic and hybrid search.\n")
    add("| | Without index | With HNSW |\n|---|---:|---:|")
    add(f"| Embedding the question (Ollama) | {ms(statistics.median(e['embed'] for e in qs))} | same |")
    add(f"| Semantic, database part | {ms(sem0)} | {ms(sem1)} |")
    add(f"| Keyword (no embedding needed) | {ms(statistics.median(e['keyword_time'] for e in qs))} | same (uses the "
        "full-text GIN index either way) |")
    add(f"| Hybrid, database part (two searches of 50 + fusion) | "
        f"{ms(statistics.median(e['hybrid_time'] for e in qs))} | {ms(statistics.median(e['hybrid_time_hnsw'] for e in qs))} |")
    add("")
    add(f"- Query plan without the index: `{out['plan_without']}` (every vector is compared, then sorted).")
    add(f"- Query plan with the index: `{out['plan_with']}`.")
    add(f"- Building the HNSW index took {out['hnsw_build']:.1f} s and added {mb(hnsw_size)}. Searches use "
        f"`hnsw.ef_search = {HNSW_EF_SEARCH}`, because an HNSW scan returns at most that many rows and hybrid "
        "search asks for 50.")
    add("- On the first try Postgres ignored the new index and kept scanning the whole table. The vectors are "
        "stored out of line (TOAST), and Postgres' planner doesn't count that cost, so the table looks cheap to "
        "scan; pgvector's README describes exactly this. Semantic search therefore switches sequential scans off "
        "for its one query (`SET enable_seqscan = off`, then `RESET`). Without an index Postgres still scans, "
        "because it has no other way.")
    add("- That switch had a side effect: it adds a huge artificial cost to the plan, which made Postgres "
        "compile the query to machine code (JIT) every time. JIT added about 27 ms to a scan of about 7 ms. JIT "
        "never pays off for queries this small, so the project's connections turn it off (`SET jit = off`).\n")
    same_sem = sum([r["id"] for r in e["semantic"]] == [r["id"] for r in e["semantic_hnsw"]] for e in qs)
    same_hyb = sum([r["id"] for r in e["hybrid"]] == [r["id"] for r in e["hybrid_hnsw"]] for e in qs)
    overlap = statistics.mean(len({r["id"] for r in e["semantic"]} & {r["id"] for r in e["semantic_hnsw"]}) / 10
                              for e in qs)
    add(f"**Did the index change the results?** HNSW is approximate. For semantic search the top 10 was identical "
        f"(same chunks, same order) for {same_sem} of the 8 questions, and on average {overlap:.0%} of the exact "
        f"top 10 was found. For hybrid search the top 10 was identical for {same_hyb} of 8.")
    diffs = [e for e in qs if [r["id"] for r in e["semantic"]] != [r["id"] for r in e["semantic_hnsw"]]]
    for e in diffs:
        exact, approx = [r["id"] for r in e["semantic"]], [r["id"] for r in e["semantic_hnsw"]]
        add(f"- *{e['topic']}*: exact `{', '.join(exact)}` vs HNSW `{', '.join(approx)}`")
    add("")
    embed_ms = statistics.median(e["embed"] for e in qs)
    add(f"In plain words: the index makes the database part of semantic search {sem0 / sem1:.0f}× faster "
        f"({ms(sem0)} → {ms(sem1)}), at the cost of {mb(hnsw_size)} of disk space. Either way a whole search, "
        f"including embedding the question ({ms(embed_ms)}), takes well under a tenth of a second, so for 5,740 "
        "chunks the index is a nice-to-have. It matters more for the agent later, which runs several searches "
        "per question, and if more volumes are added.\n")

    add("## Eight example questions\n")
    add("Top 10 of each method. Results come from exact search (no index), which is deterministic; the section "
        "above shows whether HNSW changes them. Each cell: chunk id · score, the source, the article and flags, "
        "and the start of the text. For hybrid, *sem* and *kw* are the chunk's ranks in the two lists (– = not "
        "in that list's top 50).\n")
    for i, e in enumerate(qs, 1):
        add(f"### {i}. {e['topic'].capitalize()}\n")
        add(f"**Question:** {e['question']}  ")
        add(f"Keyword search looked for: `{' '.join(e['lexemes'])}`\n")
        add(result_table(e))
        add("")
        if COMMENTS.get(i):
            add(f"**Comment:** {COMMENTS[i]}\n")
    if OVERALL:
        add("### Overall\n")
        add(OVERALL + "\n")

    add("## Near-identical chunks in the top 10\n")
    add("Many ILO conventions end with the same standard articles (entry into force, denunciation, authentic "
        "languages), and some decisions were re-issued every year with almost the same text. Two results count "
        f"as near-identical here when at least {NEAR_IDENTICAL:.0%} of their distinct words are the same "
        "(numbers and words of 1–2 letters ignored). This was chosen after trying three measures: comparing "
        "three-word sequences missed the convention clauses, which are translated with small differences, and "
        "comparing embeddings didn't separate them either, because each chunk's embedded header names a different "
        "law. On the ordinary result lists the highest word overlap between two results was about 0.36, so 0.5 "
        "doesn't flag different provisions.\n")
    add("| Question | Semantic | Keyword | Hybrid |\n|---|---:|---:|---:|")
    examples = []
    for e in qs + [{"topic": "probe: ILO convention clauses", **out["probe"]}]:
        counts = []
        for name in ("semantic", "keyword", "hybrid"):
            d = near_duplicates(e[name])
            counts.append(len(d))
            examples += [(e["topic"], name, a, b) for a, b in d]
        add(f"| {e['topic']} | {counts[0]} | {counts[1]} | {counts[2]} |")
    add("")
    add("Each number is how many of the 10 results repeat an earlier result in the same list. The last row is "
        f"an extra question, asked only for this check: \"{PROBE}\"\n")
    shown = set()
    for topic, name, a, b in examples:
        if (topic, name) in shown or len(shown) >= 3:
            continue
        shown.add((topic, name))
        add(f"- *{topic}*, {name}: `{a['id']}` ({esc(a['citation'][:50])}, {esc(a['article'] or '-')}) repeats "
            f"`{b['id']}` ({esc(b['citation'][:50])}, {esc(b['article'] or '-')}): \"{esc(a['text'][:90])}…\"")
    add("")
    add("The semantic top 10 for the probe question, to show what crowding looks like:\n")
    add("| # | Source | Article | Start of the text |\n|---:|---|---|---|")
    for r in out["probe"]["semantic"]:
        add(f"| {r['rank']} | {esc(r['citation'][:50])} | {esc(r['article'] or '-')} | {esc(r['text'][:90])}… |")
    add("")
    t = out["twins"]
    add(f"**Across the whole collection** (each chunk compared with its five nearest neighbours): "
        f"{t['identical']:,} of {t['chunks']:,} chunks ({t['identical'] / t['chunks']:.0%}) have a twin with "
        f"{IDENTICAL:.0%} or more of the same words, which is practically the same text. At {NEAR_IDENTICAL:.0%} "
        f"the count is {t['with_twin']:,}; at that level the pairs are the same clause reworded, or sibling "
        "decisions (for example two decisions setting apprentices' pay for different groups). Of those "
        f"{t['with_twin']:,}, {t['convention']:,} come from acts ratifying conventions and {t['bonus']:,} from the "
        "yearly bonus decisions. Some of the closest pairs:\n")
    for a, b, o in t["examples"][:4]:
        add(f"- `{a}` and `{b}`: {o:.0%} of their words in common")
    add("")
    if PROBE_COMMENT:
        add(f"**Comment:** {PROBE_COMMENT}\n")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    out = measure()
    (ROOT / "data/processed/search_measurements.json").write_text(json.dumps(
        {k: v for k, v in out.items() if k != "questions"} | {"questions": [
            {k: v for k, v in e.items() if k != "vector"} for e in out["questions"]]},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write(out)
    print(f"wrote {REPORT}")


def rewrite_only():
    """Regenerate the report from the last measurements (e.g. after editing COMMENTS), without measuring again."""
    out = json.loads((ROOT / "data/processed/search_measurements.json").read_text(encoding="utf-8"))
    write(out)
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    rewrite_only() if "--rewrite-only" in sys.argv else main()
