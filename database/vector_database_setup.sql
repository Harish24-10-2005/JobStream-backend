-- ============================================================================
-- VECTOR DATABASE SETUP FOR RAG (Retrieval Augmented Generation)
-- ============================================================================
-- Run this in your NEW Supabase project SQL Editor
-- Project: ybfyzmykqpcjrywuufon
-- ============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. DOCUMENTS TABLE (Vector Store for RAG)
-- ============================================================================
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    
    -- Vector Embedding (768 dimensions for Gemini text-embedding-004)
    embedding vector(768),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);

-- Vector similarity search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops);

-- Alternative: IVFFlat index (use if HNSW causes issues)
-- CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- 2. MATCH_DOCUMENTS FUNCTION (Vector Similarity Search)
-- ============================================================================
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.content,
        d.metadata,
        1 - (d.embedding <=> query_embedding) as similarity
    FROM documents d
    WHERE 
        -- Filter by user_id if provided
        (filter->>'user_id' IS NULL OR d.user_id::text = filter->>'user_id')
        AND
        -- Filter by type if provided
        (filter->>'type' IS NULL OR d.metadata->>'type' = filter->>'type')
        AND
        -- Similarity threshold
        1 - (d.embedding <=> query_embedding) > match_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- 3. ROW LEVEL SECURITY (RLS) FOR DOCUMENTS
-- ============================================================================
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Users can only view their own documents
CREATE POLICY "Users can view own documents" 
ON documents FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own documents
CREATE POLICY "Users can insert own documents" 
ON documents FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own documents
CREATE POLICY "Users can update own documents" 
ON documents FOR UPDATE 
USING (auth.uid() = user_id);

-- Users can delete their own documents
CREATE POLICY "Users can delete own documents" 
ON documents FOR DELETE 
USING (auth.uid() = user_id);

-- Service role can bypass RLS (for backend operations)
CREATE POLICY "Service role has full access" 
ON documents FOR ALL 
USING (auth.jwt()->>'role' = 'service_role');

-- ============================================================================
-- 4. HELPER FUNCTIONS
-- ============================================================================

-- Function to count documents per user
CREATE OR REPLACE FUNCTION count_user_documents(p_user_id uuid)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
    doc_count int;
BEGIN
    SELECT COUNT(*) INTO doc_count
    FROM documents
    WHERE user_id = p_user_id;
    
    RETURN doc_count;
END;
$$;

-- Function to delete all documents for a user
CREATE OR REPLACE FUNCTION delete_user_documents(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM documents WHERE user_id = p_user_id;
END;
$$;

-- Function to search documents by metadata
CREATE OR REPLACE FUNCTION search_documents_by_metadata(
    p_user_id uuid,
    p_metadata_filter jsonb DEFAULT '{}'::jsonb,
    p_limit int DEFAULT 50
)
RETURNS TABLE (
    id uuid,
    content text,
    metadata jsonb,
    created_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.content,
        d.metadata,
        d.created_at
    FROM documents d
    WHERE 
        d.user_id = p_user_id
        AND (
            p_metadata_filter = '{}'::jsonb 
            OR d.metadata @> p_metadata_filter
        )
    ORDER BY d.created_at DESC
    LIMIT p_limit;
END;
$$;

-- ============================================================================
-- 5. TRIGGERS FOR AUTO-UPDATE
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_documents_updated_at();

-- ============================================================================
-- 6. VERIFICATION QUERIES
-- ============================================================================

-- Check if pgvector is enabled
-- SELECT * FROM pg_extension WHERE extname = 'vector';

-- Check documents table structure
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name = 'documents' ORDER BY ordinal_position;

-- Check indexes
-- SELECT indexname, indexdef FROM pg_indexes 
-- WHERE tablename = 'documents';

-- Test match_documents function
-- SELECT match_documents(
--     query_embedding := array_fill(0::real, ARRAY[768])::vector,
--     match_threshold := 0.5,
--     match_count := 10,
--     filter := '{"user_id": "your-user-id"}'::jsonb
-- );

-- ============================================================================
-- DEPLOYMENT NOTES
-- ============================================================================

-- 1. This creates the 'documents' table with pgvector support
-- 2. Embeddings are 768-dimensional (for Gemini text-embedding-004)
-- 3. Uses HNSW index for fast similarity search
-- 4. RLS policies ensure user data isolation
-- 5. Backend uses service role key to bypass RLS when needed

-- IMPORTANT: After running this SQL, verify in Supabase dashboard:
-- - Table Editor → documents table exists
-- - Database → Extensions → vector is enabled
-- - API Docs → RPC → match_documents function is available

-- Connection from backend:
-- - SUPABASE_URL: https://ybfyzmykqpcjrywuufon.supabase.co
-- - SUPABASE_SERVICE_KEY: Your service role key (for write operations)
-- - Uses langchain_community.vectorstores.SupabaseVectorStore

COMMENT ON TABLE documents IS 'Vector store for RAG - stores document chunks with embeddings';
COMMENT ON COLUMN documents.embedding IS '768-dimensional vector from Gemini text-embedding-004';
COMMENT ON FUNCTION match_documents IS 'Similarity search using cosine distance';
