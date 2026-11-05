-- Embeddings from another model, for the retrieval experiment of Phase 2. Kept apart so the chunks table and its
-- bge-m3 vectors stay untouched. Safe to run again. labour_rag/embeddings.py fills the table and then builds
-- the HNSW index, because building it once is faster than updating it on every insert.
-- halfvec stores each number in 2 bytes instead of 4. pgvector can index up to 4000 dimensions of it, against 2000
-- of the plain vector type, and qwen3-embedding:4b gives 2560.

CREATE TABLE IF NOT EXISTS chunk_embeddings_qwen3_4b (
    id         text PRIMARY KEY REFERENCES chunks (id) ON DELETE CASCADE,
    embedding  halfvec(2560) NOT NULL,
    embed_hash text NOT NULL
);

COMMENT ON TABLE chunk_embeddings_qwen3_4b IS 'qwen3-embedding:4b vectors of chunks.embed_text, for a retrieval experiment';
