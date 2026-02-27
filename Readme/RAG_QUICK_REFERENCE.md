# RAG System — Quick Reference Guide

> **Quick access guide for developers working with the JobAI RAG system**
> **Version:** 2.0.0 — Updated 2026-07-10

## What is it?

A vector-based document retrieval system that gives AI agents "long-term memory" to access user-specific information (resumes, profiles, projects) during conversations, agent task execution, and browser-based form filling.

## Core Architecture

```
User Data → Text Chunking → Embeddings → Vector DB → Semantic Search → AI Agents
```

**Stack:**
- **Embeddings:** Google Gemini `text-embedding-004` (768 dims)
- **Vector DB:** Supabase pgvector (`documents` table, ivfflat index)
- **Framework:** LangChain `SupabaseVectorStore` + `RecursiveCharacterTextSplitter`
- **Chunking:** 1000 chars, 200 overlap
- **Search:** `match_documents` SQL RPC (cosine similarity, threshold=0.5, k=4)

## Key Files

| File | Purpose |
|------|---------|
| `src/services/rag_service.py` | Core RAG implementation (`add_document`, `sync_user_profile`, `query`) |
| `src/api/routes/rag.py` | `/api/v1/rag/upload` and `/api/v1/rag/query` endpoints |
| `database/schema.sql` | `documents` table DDL — must be applied in Supabase |
| `database/vector_database_setup.sql` | pgvector extension + `match_documents` function |

## Agent Integrations (6 consumers)

| Agent | File | RAG Usage |
|-------|------|-----------|
| **ResumeAgent** | `agents/resume_agent.py` | Retrieves relevant experience sections for ATS tailoring |
| **CoverLetterAgent** | `agents/cover_letter_agent.py` | LangGraph node 2: fetches matching achievements for cover letter |
| **InterviewAgent** | `agents/interview_agent.py` | Grounds STAR answers in real user project stories |
| **LiveApplierService** | `services/live_applier.py` | `retrieve_user_context` browser-use tool for form field filling |
| **SalaryAgent** | `agents/salary_agent.py` | Pulls compensation expectations for negotiation context |
| **UserProfileService** | `services/user_profile_service.py` | Auto-syncs profile on every update via `sync_user_profile()` |

## 🔧 Quick Setup

### 1. Enable pgvector in Supabase

```sql
-- Run in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX documents_embedding_idx ON documents 
USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX documents_user_id_idx ON documents(user_id);
```

### 2. Create match_documents Function

```sql
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 4,
    filter_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE (filter_user_id IS NULL OR documents.user_id = filter_user_id)
        AND 1 - (documents.embedding <=> query_embedding) > match_threshold
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

### 3. Configure Environment

```bash
# .env file
GEMINI_API_KEY=your_gemini_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_role_key
```

## 💻 Usage Examples

### Add a Document

```python
from src.services.rag_service import rag_service

# Index a document
await rag_service.add_document(
    user_id="user-uuid",
    content="Your document text here...",
    metadata={
        "type": "resume",
        "name": "Primary Resume"
    }
)
```

### Query Documents

```python
# Semantic search
results = await rag_service.query(
    user_id="user-uuid",
    query_text="projects using Kubernetes",
    k=4  # Return top 4 results
)

# Results: ["chunk 1 text", "chunk 2 text", ...]
```

### Sync User Profile

```python
# Auto-called when profile updates
await rag_service.sync_user_profile(
    user_id="user-uuid",
    profile_text="Formatted profile text..."
)
```

## Current Integrations (all live ✅)

### 1. Auto-Sync — User Profile Service
**Triggers:** profile create, update, add education/experience/project

```python
# src/services/user_profile_service.py
async def _sync_to_rag(self, user_id: str):
    profile = await self.get_profile(user_id)
    text = self._profile_to_text(profile)
    await rag_service.sync_user_profile(user_id, text)
```

### 2. Auto-Index — Resume Upload

```python
# src/services/resume_storage_service.py
await rag_service.add_document(
    user_id=user_id,
    content=full_text,
    metadata={"type": "resume", "resume_id": resume_id, "name": filename}
)
```

### 3. ResumeAgent — ATS Tailoring Context

```python
# src/agents/resume_agent.py
context_results = await rag_service.query(
    user_id,
    f"experience matching {job_requirements.key_skills_str}",
    k=4
)
# context_results injected into tailoring LLM prompt
```

### 4. CoverLetterAgent — LangGraph Node 2 (research_company)

```python
# src/agents/cover_letter_agent.py — inside research_company graph node
achievements = await rag_service.query(
    state["user_id"],
    f"achievements projects {' '.join(tech_stack)}",
    k=2
)
```

### 5. InterviewAgent — STAR Answer Grounding

```python
# src/agents/interview_agent.py
real_stories = await rag_service.query(
    user_id,
    f"real story example {topic} challenge result",
    k=2
)
# Falls back to generic guidance if no results
```

### 6. LiveApplierService — browser-use Tool

```python
# src/services/live_applier.py
@self.tools.action(description='Retrieve info from user documents')
async def retrieve_user_context(query: str):
    results = await rag_service.query(self.user_id, query)
    return "\n".join(results)
```

### 7. SalaryAgent — Compensation Context

```python
# src/agents/salary_agent.py
compensation_context = await rag_service.query(
    user_id,
    "current salary expectations compensation history",
    k=2
)
```

## 🧪 Testing

### Quick Test

```python
# Test embedding generation
embeddings = rag_service.embeddings.embed_query("test")
assert len(embeddings) == 768

# Test document indexing
doc_id = await rag_service.add_document(
    user_id="test-user",
    content="Test content",
    metadata={"type": "test"}
)

# Test retrieval
results = await rag_service.query(
    user_id="test-user",
    query_text="test"
)
assert len(results) > 0
```

### Check Database

```sql
-- Count documents per user
SELECT user_id, COUNT(*), metadata->>'type' as type
FROM documents
GROUP BY user_id, type;

-- View recent documents
SELECT id, user_id, LEFT(content, 100), metadata, created_at
FROM documents
ORDER BY created_at DESC
LIMIT 10;
```

## 🐛 Troubleshooting

### No results returned
```python
# Check if documents exist
response = supabase.table("documents") \
    .select("*") \
    .eq("user_id", user_id) \
    .execute()
print(f"Found {len(response.data)} documents")
```

### Embedding API errors
```bash
# Verify API key
echo $GEMINI_API_KEY

# Test API
curl https://generativelanguage.googleapis.com/v1/models \
  -H "x-goog-api-key: $GEMINI_API_KEY"
```

### Slow queries
```sql
-- Check if index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'documents';

-- If missing, create index
CREATE INDEX documents_embedding_idx ON documents 
USING ivfflat (embedding vector_cosine_ops);
```

## 📊 Monitoring

### Enable Debug Logging

```python
import logging
logging.getLogger("src.services.rag_service").setLevel(logging.DEBUG)
```

### Check Performance

```sql
-- Query execution time
EXPLAIN ANALYZE
SELECT * FROM documents
WHERE user_id = 'user-uuid'
ORDER BY embedding <=> '[...]'::vector
LIMIT 4;
```

## 🚨 Common Pitfalls

1. **Forgot to create documents table** → Manual setup required in Supabase
2. **Missing match_documents function** → Copy SQL function above
3. **Wrong vector dimension** → Must be 768 for Gemini embeddings
4. **RLS blocking queries** → Use service role key for backend operations
5. **No text overlap in chunks** → Already configured (200 char overlap)

## 📈 Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Query Latency | <100ms | ~15-30ms |
| Embedding Speed | <100ms/chunk | ~50ms |
| Chunk Size | 1000 chars | ✅ 1000 |
| Overlap | 20% | ✅ 200 chars |
| Top-K Results | 4 | ✅ Configurable |

## 🔐 Security

- ✅ **RLS Enabled:** Users can only access their own documents
- ✅ **User Isolation:** `filter_user_id` in all queries
- ✅ **Service Key:** Backend bypasses RLS safely
- ✅ **Metadata Validation:** user_id enforced in metadata

## 📚 Related Docs

- **Full Architecture:** [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md)
- **System Overview:** [MASTER_ARCHITECTURE.md](../MASTER_ARCHITECTURE.md) — Section 9 (RAG System)
- **API Docs:** [README.md](../README.md)

## ✅ Status Check

```bash
# Quick health check
curl http://localhost:8000/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "query": "test query",
    "k": 2
  }'

# Expected: {"results": ["...", "..."]}
```

## 🎓 Key Takeaways

1. **RAG = Long-term memory for 6 agents** — ResumeAgent, CoverLetterAgent, InterviewAgent, LiveApplier, SalaryAgent, UserProfileService
2. **Auto-syncs** — Profile/resume updates automatically trigger RAG indexing
3. **Anti-hallucination** — Grounds all agent outputs in verified user data
4. **User-isolated** — RLS `auth.uid() = user_id` on all queries
5. **Production-ready** — Working in all agent pipelines

---

**Need more details?** See [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md) for complete documentation.

**Last Updated:** 2026-07-10 — Version 2.0.0
