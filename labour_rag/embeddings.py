"""Which embedding model search uses, and how the vectors of qwen3-embedding:4b get made.

    .venv/bin/python -m labour_rag.embeddings     # embed the chunks with qwen3-embedding:4b, resuming if interrupted

Two sets of vectors are stored. bge-m3's sit in the chunks table (labour_rag.load, EMBED_MODEL in .env), and
qwen3-embedding:4b's in their own table, which this module fills from the same text (chunks.embed_text). Search uses
DEFAULT_EMBEDDING unless told otherwise; docs/retrieval-report.md has the comparison behind it.
"""

import json
import time
from collections import namedtuple

from .config import ROOT, load_settings
from .db import apply_schema, connect, friendly_errors, vector_literal
from .load import text_hash
from .model_client import ModelClient
from .normalize import normalize

QWEN3_MODEL = "qwen3-embedding:4b"
QWEN3_DIMENSIONS = 2560
QWEN3_TABLE = "chunk_embeddings_qwen3_4b"
QWEN3_INDEX = "chunk_embeddings_qwen3_4b_hnsw"
STATS_FILE = ROOT / "data/processed/embedding_stats_qwen3_4b.json"
# The model card recommends a short task instruction on the query side only, written in English; documents get none.
QUERY_INSTRUCTION = "Instruct: Given a question in Greek, retrieve passages of Greek law that answer it\nQuery: "

Embedding = namedtuple("Embedding", "model dimensions table instruction")
EMBEDDINGS = {
    "bge-m3": Embedding(None, None, "chunks", ""),      # model and size come from .env, as for labour_rag.load
    "qwen3-4b": Embedding(QWEN3_MODEL, QWEN3_DIMENSIONS, QWEN3_TABLE, QUERY_INSTRUCTION),
    "qwen3-4b-plain": Embedding(QWEN3_MODEL, QWEN3_DIMENSIONS, QWEN3_TABLE, ""),
}
DEFAULT_EMBEDDING = "qwen3-4b"


def embed_question(client, question, embedding=DEFAULT_EMBEDDING):
    """The vector of a question, cleaned like the chunks, with the chosen model."""
    chosen = EMBEDDINGS[embedding]
    return client.embed([chosen.instruction + normalize(question)], chosen.model, chosen.dimensions)[0]


def load(settings=None, log=print):
    settings = settings or load_settings()
    client = ModelClient.from_settings(settings)
    with connect(settings) as conn:
        apply_schema(conn)
        done = {row[0]: row[1] for row in conn.execute(f"SELECT id, embed_hash FROM {QWEN3_TABLE}")}
        rows = conn.execute("SELECT id, embed_text FROM chunks ORDER BY id").fetchall()
        todo = [(i, t) for i, t in rows if done.get(i) != text_hash(t)]
        log(f"{len(rows)} chunks, {len(todo)} to embed with {QWEN3_MODEL}")
        started = time.perf_counter()
        for start in range(0, len(todo), settings.embed_batch):
            part = todo[start:start + settings.embed_batch]
            vectors = client.embed((t for _, t in part), QWEN3_MODEL, QWEN3_DIMENSIONS)
            with conn.cursor() as cur:
                cur.executemany(f"INSERT INTO {QWEN3_TABLE} (id, embedding, embed_hash) VALUES (%s, %s::halfvec, %s) "
                                "ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, "
                                "embed_hash = EXCLUDED.embed_hash",
                                [(i, vector_literal(v), text_hash(t)) for (i, t), v in zip(part, vectors)])
            conn.commit()
            n = start + len(part)
            if n == len(todo) or (start // settings.embed_batch) % 20 == 0:
                log(f"  embedded {n}/{len(todo)}  {n / client.seconds:.1f} chunks/s")
        embedding_seconds = client.seconds
        total_chunks = conn.execute(f"SELECT count(*) FROM {QWEN3_TABLE}").fetchone()[0]

        index_started = time.perf_counter()
        conn.execute(f"CREATE INDEX IF NOT EXISTS {QWEN3_INDEX} ON {QWEN3_TABLE} USING hnsw (embedding halfvec_cosine_ops)")
        conn.commit()
        index_seconds = time.perf_counter() - index_started
        size = conn.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{QWEN3_TABLE}'))").fetchone()[0]
    stats = {"model": QWEN3_MODEL, "chunks": total_chunks, "embedded": len(todo), "batch": settings.embed_batch,
             "embedding_seconds": round(embedding_seconds, 1), "index_seconds": round(index_seconds, 1),
             "total_seconds": round(time.perf_counter() - started, 1), "tokens": client.tokens, "table_size": size}
    if todo:
        stats["chunks_per_second"] = round(len(todo) / embedding_seconds, 2)
        STATS_FILE.write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log(f"done: {json.dumps(stats)}")
    return stats


if __name__ == "__main__":
    friendly_errors(load)
