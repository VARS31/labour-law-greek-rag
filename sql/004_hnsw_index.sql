-- Approximate nearest-neighbour index for semantic search (pgvector HNSW, cosine distance). Safe to run again.
-- Added after measuring search without it; see docs/search-report.md. Default build settings (m = 16,
-- ef_construction = 64). At query time the connection sets hnsw.ef_search = 100 (labour_rag/db.py), because an
-- HNSW scan returns at most ef_search rows and hybrid search asks for 50 candidates.

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
