-- Migration: Switch chunks embedding index from IVFFlat to HNSW
-- This does NOT affect any data — only the index structure used for vector search.
-- HNSW provides faster queries at the cost of slightly slower index build time.
--
-- Run with: docker exec -i apoioprocessual-db psql -U legal -d legal_assistant < scripts/migrate_hnsw_index.sql

-- Drop the old IVFFlat index
DROP INDEX IF EXISTS idx_chunks_embedding;

-- Create new HNSW index (may take a few minutes depending on data volume)
-- m=16: max connections per node (higher = better recall, more memory)
-- ef_construction=64: build-time search width (higher = better index quality, slower build)
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Verify the index was created
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'chunks' AND indexname = 'idx_chunks_embedding';
