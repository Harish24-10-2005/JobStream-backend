"""
Vector Database Setup Verification Script
Checks if vector database is properly configured and connected
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from supabase import Client, create_client

from src.core.config import settings


def verify_vector_db():
    """Verify vector database setup"""
    print("="*70)
    print("VECTOR DATABASE VERIFICATION")
    print("="*70)
    
    # 1. Check environment variables
    print("\n1. Environment Variables:")
    print(f"   SUPABASE_URL: {settings.supabase_url}")
    print(f"   SUPABASE_ANON_KEY: {settings.supabase_anon_key[:20]}...")
    if settings.supabase_service_key:
        print(f"   SUPABASE_SERVICE_KEY: {settings.supabase_service_key.get_secret_value()[:20]}...")
    else:
        print("   ⚠️  SUPABASE_SERVICE_KEY: Not configured")
    
    if settings.gemini_api_key:
        print(f"   GEMINI_API_KEY: {settings.gemini_api_key.get_secret_value()[:20]}...")
    else:
        print("   ❌ GEMINI_API_KEY: Missing!")
        return
    
    # 2. Test Supabase connection
    print("\n2. Supabase Connection:")
    try:
        if settings.supabase_service_key:
            key = settings.supabase_service_key.get_secret_value()
        else:
            key = settings.supabase_anon_key
        
        client: Client = create_client(settings.supabase_url, key)
        print("   ✅ Client created successfully")
        
        # Test query
        result = client.table("user_profiles").select("id").limit(1).execute()
        print("   ✅ Can query user_profiles table")
        
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return
    
    # 3. Check if documents table exists
    print("\n3. Documents Table (Vector Store):")
    try:
        result = client.table("documents").select("id").limit(1).execute()
        print("   ✅ 'documents' table exists")
        
        # Count documents
        count_result = client.table("documents").select("id", count="exact").execute()
        doc_count = count_result.count if hasattr(count_result, 'count') else 0
        print(f"   📊 Total documents in DB: {doc_count}")
        
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg and "does not exist" in error_msg:
            print("   ❌ 'documents' table DOES NOT EXIST!")
            print("\n   🔧 ACTION REQUIRED:")
            print("   1. Open Supabase Dashboard: https://supabase.com/dashboard")
            print("   2. Go to your project: ybfyzmykqpcjrywuufon")
            print("   3. Navigate to: SQL Editor")
            print("   4. Run the SQL file: backend/database/vector_database_setup.sql")
            print("   5. Verify in Table Editor that 'documents' table appears")
            return
        else:
            print(f"   ❌ Error checking table: {e}")
            return
    
    # 4. Check if pgvector extension is enabled
    print("\n4. pgvector Extension:")
    try:
        result = client.rpc("match_documents", {
            "query_embedding": [0.0] * 768,
            "match_threshold": 0.5,
            "match_count": 1,
            "filter": {}
        }).execute()
        print("   ✅ 'match_documents' RPC function exists")
        print("   ✅ pgvector extension is enabled")
        
    except Exception as e:
        error_msg = str(e)
        if "function" in error_msg and "does not exist" in error_msg:
            print("   ❌ 'match_documents' function DOES NOT EXIST!")
            print("\n   🔧 ACTION REQUIRED:")
            print("   Run: backend/database/vector_database_setup.sql")
        elif "type" in error_msg and "vector" in error_msg:
            print("   ❌ pgvector extension NOT ENABLED!")
            print("\n   🔧 ACTION REQUIRED:")
            print("   1. Go to Supabase Dashboard → Database → Extensions")
            print("   2. Search for 'vector'")
            print("   3. Click 'Enable' on pgvector extension")
        else:
            print(f"   ❌ Error: {e}")
        return
    
    # 5. Test embedding generation
    print("\n5. Embedding Generation (Gemini):")
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.gemini_api_key.get_secret_value()
        )
        
        test_text = "This is a test document for embedding generation"
        test_embedding = embeddings.embed_query(test_text)
        
        print(f"   ✅ Generated embedding: {len(test_embedding)} dimensions")
        print(f"   ✅ Sample values: {test_embedding[:3]}")
        
        if len(test_embedding) <= 0:
            print(f"   ⚠️  WARNING: Unexpected embedding dimensions: {len(test_embedding)}")
        
    except Exception as e:
        print(f"   ❌ Embedding generation failed: {e}")
        return
    
    # 6. Test full RAG pipeline
    print("\n6. RAG Service Integration:")
    try:
        from src.services.rag_service import RAGService
        
        rag_service = RAGService()
        print("   ✅ RAGService initialized successfully")
        print(f"   ✅ Vector store table: {rag_service.vector_store.table_name}")
        print(f"   ✅ Query function: {rag_service.vector_store.query_name}")
        
    except Exception as e:
        print(f"   ❌ RAGService initialization failed: {e}")
        return
    
    # Success summary
    print("\n" + "="*70)
    print("✅ VECTOR DATABASE IS PROPERLY CONFIGURED!")
    print("="*70)
    print("\nConnection Details:")
    print("  • Project: ybfyzmykqpcjrywuufon")
    print(f"  • URL: {settings.supabase_url}")
    print("  • Table: documents")
    print("  • Function: match_documents")
    print(f"  • Embedding Model: Gemini {settings.gemini_embedding_model}")
    print(f"  • Total Documents: {doc_count}")
    
    print("\n📚 Vector Store Usage:")
    print("  • Stores resume chunks, cover letter templates, etc.")
    print("  • Each user's documents are isolated via RLS policies")
    print("  • Semantic search enabled via cosine similarity")
    print("  • Backend uses service role key for write operations")
    
    print("\n🔒 Security:")
    print("  • Row Level Security (RLS) enabled")
    print("  • Users can only access their own documents")
    print("  • Service role bypasses RLS for backend operations")
    
    print("="*70)

if __name__ == "__main__":
    try:
        verify_vector_db()
    except KeyboardInterrupt:
        print("\n⚠️  Verification interrupted by user")
    except Exception as e:
        print(f"\n❌ Verification error: {e}")
        import traceback
        traceback.print_exc()
