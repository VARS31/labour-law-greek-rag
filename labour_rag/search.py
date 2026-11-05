"""Search the chunks three ways:

  semantic  nearest embeddings (cosine similarity; embeddings.DEFAULT_EMBEDDING chooses whose vectors)
  keyword   Postgres full-text search: accent-insensitive, Greek stopwords removed, any query word may match
  hybrid    Reciprocal Rank Fusion (RRF) of the two lists

fuse() has the ways of combining the lists that docs/retrieval-report.md compares. The question is cleaned with the same normalisation as the chunks (labour_rag.normalize).

    .venv/bin/python -m labour_rag.search "κανονική άδεια εργαζομένων" [-k 10]
"""

import argparse
import shutil
import textwrap

from .db import connect, friendly_errors, vector_literal
from .embeddings import DEFAULT_EMBEDDING, EMBEDDINGS, embed_question
from .law_mentions import names_a_law
from .model_client import ModelClient
from .normalize import normalize

CANDIDATES = 50     # how many results hybrid takes from each list before fusing
RRF_K = 60          # the usual RRF constant: score = sum of 1 / (RRF_K + rank)
FUSIONS = ("semantic", "rrf", "weighted", "reserved", "law-lookup")     # simplest first
DEFAULT_FUSION = "semantic"     # chosen by experiment, docs/retrieval-report.md; "rrf" is the old default
SEMANTIC_WEIGHT = 2     # "weighted": a place in the semantic list counts this many times a place in the keyword list
SEMANTIC_PLACES = 6     # "reserved" and "law-lookup": the first places go to semantic search…
KEYWORD_PLACES = 2      # … and the next ones to keyword chunks that semantic search hasn't placed yet
_COLUMNS = "id, doc_id, citation, citation_fallback, article, title, year, is_note, is_stub, text"

_SEMANTIC = f"""
    SELECT {_COLUMNS}, 1 - (embedding <=> %(v)s::vector) AS score
    FROM chunks
    ORDER BY embedding <=> %(v)s::vector
    LIMIT %(k)s
"""
# Other embeddings have their own table of vectors, stored as halfvec.
_SEMANTIC_OWN_TABLE = f"""
    WITH nearest AS (
        SELECT id, embedding <=> %(v)s::halfvec AS distance
        FROM {{table}}
        ORDER BY embedding <=> %(v)s::halfvec
        LIMIT %(k)s
    )
    SELECT {_COLUMNS}, 1 - distance AS score
    FROM nearest JOIN chunks USING (id)
    ORDER BY distance
"""
# The query words, after the same processing as the chunks, joined with OR ("|"). Ranked by ts_rank with
# length normalisation (option 1), so long chunks don't win just by repeating a word.
_KEYWORD = f"""
    WITH q AS (
        SELECT string_agg(quote_literal(lexeme), ' | ')::tsquery AS query
        FROM unnest(to_tsvector('greek_labour', %(q)s))
    )
    SELECT {_COLUMNS}, ts_rank(fts, q.query, 1) AS score
    FROM chunks, q
    WHERE q.query IS NOT NULL AND fts @@ q.query
    ORDER BY score DESC, id
    LIMIT %(k)s
"""


def _rows(cursor):
    names = [d.name for d in cursor.description]
    return [dict(zip(names, row), rank=i) for i, row in enumerate(cursor.fetchall(), 1)]


def query_lexemes(conn, question):
    """The words keyword search will look for, after normalisation, stopwords and stemming."""
    return conn.execute("SELECT array(SELECT lexeme FROM unnest(to_tsvector('greek_labour', %s)))",
                        [normalize(question)]).fetchone()[0]


def semantic(conn, client, question, k=10, vector=None, embedding=DEFAULT_EMBEDDING):
    """Nearest chunks by cosine similarity. Uses the HNSW index when it exists.

    The vectors are stored out of line (TOAST) and Postgres' planner doesn't count that cost, so on its own it
    picks a full table scan even when the HNSW index is there. pgvector's README suggests switching sequential
    scans off for such queries; without an index Postgres still scans, because it has no other way."""
    vector = vector or embed_question(client, question, embedding)
    table = EMBEDDINGS[embedding].table
    query = _SEMANTIC if table == "chunks" else _SEMANTIC_OWN_TABLE.format(table=table)
    conn.execute("SET enable_seqscan = off")
    try:
        return _rows(conn.execute(query, {"v": vector_literal(vector), "k": k}))
    finally:
        conn.execute("RESET enable_seqscan")


def explain_semantic(conn, vector, k=10):
    """The query plan semantic() gets, as a short list of plan steps."""
    conn.execute("SET enable_seqscan = off")
    try:
        plan = conn.execute("EXPLAIN (FORMAT JSON) " + _SEMANTIC, {"v": vector_literal(vector), "k": k}).fetchone()[0]
    finally:
        conn.execute("RESET enable_seqscan")
    nodes, stack = [], [plan[0]["Plan"]]
    while stack:
        node = stack.pop()
        nodes.append(node["Node Type"] + (f" using {node['Index Name']}" if "Index Name" in node else ""))
        stack.extend(node.get("Plans", []))
    return nodes


def keyword(conn, question, k=10):
    return _rows(conn.execute(_KEYWORD, {"q": normalize(question), "k": k}))


def rrf_fuse(lists, k=10, rrf_k=RRF_K, weights=None):
    """Reciprocal Rank Fusion of {name: ranked results}: a chunk scores weight / (rrf_k + rank) in each list it
    appears in, summed (weights default to 1). Each result keeps its rank in every list as <name>_rank (None if
    absent)."""
    fused = {}
    for name, results in lists.items():
        for r in results:
            entry = fused.setdefault(r["id"], {**r, "score": 0.0, **{f"{n}_rank": None for n in lists}})
            entry["score"] += (weights or {}).get(name, 1) / (rrf_k + r["rank"])
            entry[f"{name}_rank"] = r["rank"]
    ranked = sorted(fused.values(), key=lambda r: (-r["score"], r["id"]))[:k]
    return [dict(r, rank=i) for i, r in enumerate(ranked, 1)]


def reserved_places(semantic_results, keyword_results, first=SEMANTIC_PLACES, added=KEYWORD_PLACES):
    """Semantic's first places, then the best keyword chunks not among them, then the rest of semantic. So keyword
    search can add what semantic missed, but can't push out what semantic ranked highest."""
    head = semantic_results[:first]
    extra = [r for r in keyword_results if r["id"] not in {h["id"] for h in head}][:added]
    placed = {r["id"] for r in head + extra}
    return head + extra + [r for r in semantic_results[first:] if r["id"] not in placed]


def _numbered(chunks, lists, k):
    """The first k chunks, numbered, each with its rank in every list as <name>_rank."""
    ranks = {name: {r["id"]: r["rank"] for r in results} for name, results in lists.items()}
    return [{**r, "rank": i, **{f"{name}_rank": ranks[name].get(r["id"]) for name in lists}}
            for i, r in enumerate(chunks[:k], 1)]


def fuse(fusion, semantic_results, keyword_results, question, k=10):
    """One ranked list from the two, by the chosen way (see FUSIONS). Every result keeps its rank in each list as
    semantic_rank and keyword_rank, as rrf_fuse does."""
    lists = {"semantic": semantic_results, "keyword": keyword_results}
    if fusion == "rrf":
        return rrf_fuse(lists, k)
    if fusion == "weighted":
        return rrf_fuse(lists, k, weights={"semantic": SEMANTIC_WEIGHT})
    if fusion == "semantic" or (fusion == "law-lookup" and not names_a_law(normalize(question))):
        chunks = semantic_results
    elif fusion in ("reserved", "law-lookup"):
        chunks = reserved_places(semantic_results, keyword_results)
    else:
        raise ValueError(f"unknown fusion: {fusion}")
    return _numbered(chunks, lists, k)


def best_similarity(lists):
    """One ranked list from the semantic lists of several queries. Every chunk keeps its highest similarity to any one
    query, so being found by many queries earns nothing, which is what went wrong with RRF. The scores can be compared
    because all the queries are embedded by the same model and searched in the same vectors."""
    best = {}
    for results in lists:
        for r in results:
            if r["id"] not in best or r["score"] > best[r["id"]]["score"]:
                best[r["id"]] = r
    ordered = sorted(best.values(), key=lambda r: (-r["score"], r["id"]))
    return [dict(r, rank=i) for i, r in enumerate(ordered, 1)]


def multi_query(conn, client, queries, keyword_query="", k=10, candidates=CANDIDATES, embedding=DEFAULT_EMBEDDING):
    """Search each query semantically and combine by best_similarity. If there is a keyword query, keyword search may add
    chunks after semantic's first places, as in reserved_places. Returns (ranked chunks, the two lists they came from)."""
    semantic_results = best_similarity([semantic(conn, client, q, candidates, embedding=embedding) for q in queries])
    keyword_results = keyword(conn, keyword_query, candidates) if keyword_query else []
    chunks = reserved_places(semantic_results, keyword_results) if keyword_results else semantic_results
    lists = {"semantic": semantic_results, "keyword": keyword_results}
    return _numbered(chunks, lists, k), lists


def ranked(conn, client, question, k=10, fusion=DEFAULT_FUSION, candidates=CANDIDATES, vector=None,
           embedding=DEFAULT_EMBEDDING):
    """The k best chunks for a question, by the chosen way of combining semantic and keyword search."""
    keyword_results = [] if fusion == "semantic" else keyword(conn, question, candidates)
    return fuse(fusion, semantic(conn, client, question, candidates, vector, embedding), keyword_results, question, k)


def hybrid(conn, client, question, k=10, candidates=CANDIDATES, vector=None, embedding=DEFAULT_EMBEDDING):
    return ranked(conn, client, question, k, "rrf", candidates, vector, embedding)


def search_all(conn, client, question, k=10):
    vector = embed_question(client, question)             # embed once, use for both semantic and hybrid
    return {"semantic": semantic(conn, client, question, k, vector),
            "keyword": keyword(conn, question, k),
            "hybrid": hybrid(conn, client, question, k, vector=vector)}


def flags(r):
    return " ".join(f for f, on in (("note", r["is_note"]), ("stub", r["is_stub"])) if on) or "-"


def _cell(r, width):
    if r is None:
        return []
    lines = [f"{r['rank']:>2}. {r['id']}   score {r['score']:.4f}"]
    lines += textwrap.wrap(r["citation"], width, max_lines=2, placeholder="…")
    lines += textwrap.wrap(f"{r['article'] or '-'}   [{flags(r)}]", width, max_lines=1, placeholder="…")
    lines += textwrap.wrap(r["text"][:150], width)
    return lines


def print_side_by_side(question, results, k=10):
    width = max(36, (shutil.get_terminal_size((190, 40)).columns - 6) // 3)
    names = list(results)
    print(f"\n{question}\n")
    print(" │ ".join(name.upper().ljust(width) for name in names))
    print("─┼─".join("─" * width for _ in names))
    for i in range(k):
        cells = [_cell(results[n][i] if i < len(results[n]) else None, width) for n in names]
        for line in range(max(map(len, cells))):
            print(" │ ".join((c[line] if line < len(c) else "").ljust(width) for c in cells))
        print("─┼─".join("─" * width for _ in names))


def main():
    parser = argparse.ArgumentParser(description="Search the labour-law chunks three ways and compare.")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=10, help="results per method (default 10)")
    args = parser.parse_args()
    with connect() as conn:
        print_side_by_side(args.question, search_all(conn, ModelClient.from_settings(), args.question, args.k), args.k)


if __name__ == "__main__":
    friendly_errors(main)
