"""Load the chunks into Postgres, with embeddings.

    .venv/bin/python -m labour_rag.load [--file data/processed/labour_chunks.jsonl]

Safe to run again: rows are upserted by chunk id, a chunk is embedded only when it is new or its embed_text
or the model changed (embed_hash, embed_model), and rows no longer in the file are deleted. Embeddings are
committed batch by batch, so an interrupted run continues where it stopped.
"""

import argparse
import hashlib
import json
import time

from .config import ROOT, load_settings
from .db import apply_schema, connect, vector_literal
from .model_client import ModelClient

CHUNKS_FILE = ROOT / "data/processed/labour_chunks.jsonl"
STATS_FILE = ROOT / "data/processed/embedding_stats.json"
FIELDS = ["id", "doc_id", "seq", "split", "volume", "chapter", "subject", "act_type", "act_abbr", "act_number",
          "year", "fek", "title", "citation", "citation_fallback", "method", "kind", "article", "article_numbers",
          "part", "parts", "words", "is_stub", "is_note", "repeal_sentences", "text", "embed_text"]
UPSERT = (f"INSERT INTO chunks ({', '.join(FIELDS)}) VALUES ({', '.join(['%s'] * len(FIELDS))}) "
          f"ON CONFLICT (id) DO UPDATE SET {', '.join(f'{f} = EXCLUDED.{f}' for f in FIELDS[1:])}")
# Unchanged rows are left alone, so a re-run doesn't leave dead row versions behind. --rewrite updates every row
# anyway, which recomputes the stored full-text column (needed after editing sql/greek_labour.stop).
ONLY_CHANGED = (f" WHERE ({', '.join(f'chunks.{f}' for f in FIELDS[1:])}) "
                f"IS DISTINCT FROM ({', '.join(f'EXCLUDED.{f}' for f in FIELDS[1:])})")
SET_EMBEDDING = "UPDATE chunks SET embedding = %s::vector, embed_model = %s, embed_hash = %s WHERE id = %s"


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _duration(seconds):
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


def load(path=CHUNKS_FILE, settings=None, log=print, rewrite=False):
    settings = settings or load_settings()
    client = ModelClient.from_settings(settings)
    chunks = [json.loads(line) for line in open(path, encoding="utf-8")]
    started = time.perf_counter()

    with connect(settings) as conn:
        apply_schema(conn)
        done = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT id, embed_hash, embed_model FROM chunks")}

        with conn.cursor() as cur:
            cur.executemany(UPSERT if rewrite else UPSERT + ONLY_CHANGED, [[c[f] for f in FIELDS] for c in chunks])
        ids = [c["id"] for c in chunks]
        stale = conn.execute("DELETE FROM chunks WHERE NOT (id = ANY(%s))", [ids]).rowcount
        conn.commit()
        new = sum(1 for c in chunks if c["id"] not in done)
        log(f"{len(chunks)} chunks in the file: {new} new, {stale} stale rows deleted"
            + (", every row rewritten" if rewrite else ""))

        todo = [c for c in chunks if done.get(c["id"]) != (text_hash(c["embed_text"]), client.embed_model)]
        log(f"{len(todo)} chunks to embed with {client.embed_model} ({len(chunks) - len(todo)} already up to date)")
        batch = settings.embed_batch
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            vectors = client.embed(c["embed_text"] for c in part)
            with conn.cursor() as cur:
                cur.executemany(SET_EMBEDDING, [(vector_literal(v), client.embed_model, text_hash(c["embed_text"]),
                                                 c["id"]) for c, v in zip(part, vectors)])
            conn.commit()
            n = i + len(part)
            if n == len(todo) or (i // batch) % 20 == 0:
                rate = n / client.seconds if client.seconds else 0
                eta = (len(todo) - n) / rate if rate else 0
                log(f"  embedded {n}/{len(todo)}  {rate:.1f} chunks/s  ETA {_duration(eta)}")
        conn.commit()
        conn.autocommit = True                 # VACUUM can't run inside a transaction
        conn.execute("VACUUM (ANALYZE) chunks")  # frees dead row versions for reuse, updates planner statistics

    stats = {"model": client.embed_model, "chunks": len(chunks), "embedded": len(todo), "batch": batch,
             "embedding_seconds": round(client.seconds, 1), "total_seconds": round(time.perf_counter() - started, 1),
             "tokens": client.tokens}
    if todo:
        stats["chunks_per_second"] = round(len(todo) / client.seconds, 2)
        STATS_FILE.write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log(f"done: embedding took {_duration(client.seconds)} for {len(todo)} chunks ({client.tokens} tokens); "
        f"total {_duration(stats['total_seconds'])}")
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", default=CHUNKS_FILE)
    parser.add_argument("--rewrite", action="store_true",
                        help="update every row, e.g. to recompute the full-text column after editing the stop list")
    args = parser.parse_args()
    load(args.file, rewrite=args.rewrite)


if __name__ == "__main__":
    main()
