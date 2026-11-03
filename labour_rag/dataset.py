"""Load the Greek Legal Code parquet files with all three labels per document."""

import json

import duckdb

LEVELS = ["volume", "chapter", "subject"]
SPLITS = ["train", "validation", "test"]
LABOUR_VOLUME = 41  # ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ


def load_documents(raw_dir, volume=None):
    """Documents as dicts {doc_id, split, text, volume, chapter, subject} (label names, not ids).

    doc_id is the 0-based position in train, then validation, then test (same as in Phase 0). The three
    configs hold the same texts in the same order, so their labels are joined by position.
    """
    con = duckdb.connect()
    names, labels, texts = {}, {}, {}
    for level in LEVELS:
        meta = con.execute(f"select value from parquet_kv_metadata('{raw_dir}/{level}/train.parquet') "
                           "where key = 'huggingface'").fetchall()[0][0]
        names[level] = json.loads(meta)["info"]["features"]["label"]["names"]
        for split in SPLITS:
            rows = con.execute(f"select text, label from read_parquet('{raw_dir}/{level}/{split}.parquet')").fetchall()
            texts[level, split] = [r[0] for r in rows]
            labels[level, split] = [r[1] for r in rows]

    docs = []
    for split in SPLITS:
        if not texts["volume", split] == texts["chapter", split] == texts["subject", split]:
            raise ValueError(f"{split}: the three label configs are not row-aligned")
        for row, text in enumerate(texts["volume", split]):
            doc_id = len(docs)
            docs.append({"doc_id": doc_id, "split": split, "text": text,
                         **{level: names[level][labels[level, split][row]] for level in LEVELS},
                         "volume_id": labels["volume", split][row]})
    if volume is not None:
        docs = [d for d in docs if d["volume_id"] == volume]
    return docs
