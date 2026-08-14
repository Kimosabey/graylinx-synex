-- pgvector, for the 768-dimension embeddings the local model produces.
-- The dimension is locked to the model: changing `nomic-embed-text` invalidates every stored
-- vector, which is why the embedding role is excluded from run-time editing.
CREATE EXTENSION IF NOT EXISTS vector;
