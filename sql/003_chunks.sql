-- The chunks table: one row per line of data/processed/labour_chunks.jsonl, plus its embedding and a
-- full-text column. Safe to run again. No vector index here (see 004_hnsw_index.sql).

CREATE TABLE IF NOT EXISTS chunks (
    id                text PRIMARY KEY,
    doc_id            integer NOT NULL,
    seq               integer NOT NULL,
    split             text,
    volume            text,
    chapter           text,
    subject           text,
    act_type          text,
    act_abbr          text,
    act_number        text,
    year              integer,
    fek               text,
    title             text,
    citation          text NOT NULL,
    citation_fallback boolean NOT NULL,
    method            text,
    kind              text,
    article           text,
    article_numbers   integer[],
    part              integer,
    parts             integer,
    words             integer,
    is_stub           boolean NOT NULL,
    is_note           boolean NOT NULL,
    repeal_sentences  text[],
    text              text NOT NULL,
    embed_text        text NOT NULL,
    embedding         vector(1024),
    embed_model       text,
    embed_hash        text,
    fts               tsvector GENERATED ALWAYS AS (to_tsvector('greek_labour', embed_text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin (fts);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (doc_id, seq);

COMMENT ON TABLE chunks IS 'Chunks of the labour-law volume (Greek Legal Code, volume 41), with embedding and full-text column';
COMMENT ON COLUMN chunks.id IS 'Stable chunk id, glc-<document>-<sequence>, e.g. glc-03244-002';
COMMENT ON COLUMN chunks.doc_id IS 'Document number: 0-based position in train, then validation, then test';
COMMENT ON COLUMN chunks.seq IS 'Position of the chunk inside its document, from 0';
COMMENT ON COLUMN chunks.split IS 'Split of the original dataset (train/validation/test); not used for search';
COMMENT ON COLUMN chunks.volume IS 'Volume label (broadest topic), here always ΕΡΓΑΤΙΚΗ ΝΟΜΟΘΕΣΙΑ';
COMMENT ON COLUMN chunks.chapter IS 'Chapter label (middle topic level)';
COMMENT ON COLUMN chunks.subject IS 'Subject label (narrowest topic level)';
COMMENT ON COLUMN chunks.act_type IS 'Type of act from the header, e.g. Προεδρικό διάταγμα; NULL if not found';
COMMENT ON COLUMN chunks.act_abbr IS 'Abbreviation of the act type, e.g. Π.Δ.';
COMMENT ON COLUMN chunks.act_number IS 'Number of the act, e.g. 70 or 98168/7185';
COMMENT ON COLUMN chunks.year IS 'Year of publication from the header date';
COMMENT ON COLUMN chunks.fek IS 'Government Gazette reference, e.g. Α΄ 31';
COMMENT ON COLUMN chunks.title IS 'Title of the act from the header';
COMMENT ON COLUMN chunks.citation IS 'How the chunk names its source: Π.Δ. 70/1990, or the fallback «title» (chapter, year)';
COMMENT ON COLUMN chunks.citation_fallback IS 'True when the header had no act number, so the fallback form is used';
COMMENT ON COLUMN chunks.method IS 'How the document was cut: article, paragraph, size or whole';
COMMENT ON COLUMN chunks.kind IS 'What this chunk is: preamble, article, paragraph, whole or size (a window)';
COMMENT ON COLUMN chunks.article IS 'Article label(s), e.g. Άρθρο 28 or Προοίμιο, Άρθρο 1';
COMMENT ON COLUMN chunks.article_numbers IS 'Article numbers as integers; a range like Άρθρα 13-19 lists every number';
COMMENT ON COLUMN chunks.part IS 'Window number when a long piece was cut (1-based)';
COMMENT ON COLUMN chunks.parts IS 'Number of windows the piece was cut into';
COMMENT ON COLUMN chunks.words IS 'Length of the chunk text in words';
COMMENT ON COLUMN chunks.is_stub IS 'True when the whole document is under 30 words';
COMMENT ON COLUMN chunks.is_note IS 'True when the chunk is mainly an editorial note, not law text';
COMMENT ON COLUMN chunks.repeal_sentences IS 'Short sentences around past-tense repeal verbs (Κατηργήθη δια …), for later';
COMMENT ON COLUMN chunks.text IS 'Cleaned chunk text';
COMMENT ON COLUMN chunks.embed_text IS 'Short source header + newline + text; this is what is embedded and keyword-indexed';
COMMENT ON COLUMN chunks.embedding IS 'Embedding of embed_text (1024 numbers, bge-m3 by default)';
COMMENT ON COLUMN chunks.embed_model IS 'Ollama model that made the embedding';
COMMENT ON COLUMN chunks.embed_hash IS 'SHA-256 of embed_text; on reload, a chunk is re-embedded only if this or the model changed';
COMMENT ON COLUMN chunks.fts IS 'Full-text vector of embed_text in the greek_labour configuration (accent-insensitive, stopwords removed)';
