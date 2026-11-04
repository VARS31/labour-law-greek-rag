"""A second embedding model, kept apart from the chunks table, to compare it with bge-m3 on retrieval.

    .venv/bin/python -m labour_rag.embed_experiment     # embed the chunks with the model, resuming if interrupted

Same input as bge-m3 (chunks.embed_text), same keyword search and same fusion, so only the vectors differ.
"""

import dataclasses
import json
import time

from .config import ROOT, load_settings
from .db import apply_schema, connect, friendly_errors, vector_literal
from .load import text_hash
from .model_client import ModelClient
from .normalize import normalize
from .search import _COLUMNS, _rows

MODEL = "qwen3-embedding:4b"
DIMENSIONS = 2560
TABLE = "chunk_embeddings_qwen3_4b"
INDEX = "chunk_embeddings_qwen3_4b_hnsw"
STATS_FILE = ROOT / "data/processed/embedding_stats_qwen3_4b.json"
# The model card recommends a short task instruction on the query side only, written in English; documents get none.
QUERY_INSTRUCTION = "Instruct: Given a question in Greek, retrieve passages of Greek law that answer it\nQuery: "

_SEMANTIC = f"""
    WITH nearest AS (
        SELECT id, embedding <=> %(v)s::halfvec AS distance
        FROM {TABLE}
        ORDER BY embedding <=> %(v)s::halfvec
        LIMIT %(k)s
    )
    SELECT {_COLUMNS}, 1 - distance AS score
    FROM nearest JOIN chunks USING (id)
    ORDER BY distance
"""


def client(settings=None):
    """A model client for this model; everything else comes from .env."""
    settings = settings or load_settings()
    return ModelClient.from_settings(dataclasses.replace(settings, embed_model=MODEL, embed_dim=DIMENSIONS))


def embed_question(model_client, question, instruction=True):
    text = normalize(question)
    return model_client.embed([QUERY_INSTRUCTION + text if instruction else text])[0]


def semantic(conn, vector, k=50):
    """Nearest chunks by this model's vectors. Sequential scans are off for the reason given in search.semantic."""
    conn.execute("SET enable_seqscan = off")
    try:
        return _rows(conn.execute(_SEMANTIC, {"v": vector_literal(vector), "k": k}))
    finally:
        conn.execute("RESET enable_seqscan")


def load(settings=None, log=print):
    settings = settings or load_settings()
    model = client(settings)
    with connect(settings) as conn:
        apply_schema(conn)
        done = {row[0]: row[1] for row in conn.execute(f"SELECT id, embed_hash FROM {TABLE}")}
        rows = conn.execute("SELECT id, embed_text FROM chunks ORDER BY id").fetchall()
        todo = [(i, t) for i, t in rows if done.get(i) != text_hash(t)]
        log(f"{len(rows)} chunks, {len(todo)} to embed with {MODEL}")
        started = time.perf_counter()
        for start in range(0, len(todo), settings.embed_batch):
            part = todo[start:start + settings.embed_batch]
            vectors = model.embed(t for _, t in part)
            with conn.cursor() as cur:
                cur.executemany(f"INSERT INTO {TABLE} (id, embedding, embed_hash) VALUES (%s, %s::halfvec, %s) "
                                "ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, "
                                "embed_hash = EXCLUDED.embed_hash",
                                [(i, vector_literal(v), text_hash(t)) for (i, t), v in zip(part, vectors)])
            conn.commit()
            n = start + len(part)
            if n == len(todo) or (start // settings.embed_batch) % 20 == 0:
                log(f"  embedded {n}/{len(todo)}  {n / model.seconds:.1f} chunks/s")
        embedding_seconds = model.seconds
        total_chunks = conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]

        index_started = time.perf_counter()
        conn.execute(f"CREATE INDEX IF NOT EXISTS {INDEX} ON {TABLE} USING hnsw (embedding halfvec_cosine_ops)")
        conn.commit()
        index_seconds = time.perf_counter() - index_started
        size = conn.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{TABLE}'))").fetchone()[0]
    stats = {"model": MODEL, "chunks": total_chunks, "embedded": len(todo), "batch": settings.embed_batch,
             "embedding_seconds": round(embedding_seconds, 1), "index_seconds": round(index_seconds, 1),
             "total_seconds": round(time.perf_counter() - started, 1), "tokens": model.tokens, "table_size": size}
    if todo:
        stats["chunks_per_second"] = round(len(todo) / embedding_seconds, 2)
        STATS_FILE.write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log(f"done: {json.dumps(stats)}")
    return stats


if __name__ == "__main__":
    friendly_errors(load)
