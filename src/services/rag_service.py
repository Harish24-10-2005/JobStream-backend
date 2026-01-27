
import logging
from typing import List, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client, Client
from src.core.config import settings

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.supabase_url = settings.supabase_url
        # Use service key if available for RAG (better for writing), else anon
        if settings.supabase_service_key:
            self.supabase_key = settings.supabase_service_key.get_secret_value()
        else:
            self.supabase_key = settings.supabase_anon_key
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        # However, for backend operations, we usually use the service role key to bypass RLS if we manage it manualy,
        # OR we use the logged-in user's token.
        # Since this service runs on backend and "enforces" user_id via arguments, we can use the admin key (service role)
        # IF we trust the backend. Or we can use the anon key.
        # Based on existing codebase, I'll use the configured key.
        self.client: Client = create_client(self.supabase_url, self.supabase_key)

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        )
        
        self.vector_store = SupabaseVectorStore(
            client=self.client,
            embedding=self.embeddings,
            table_name="documents",
            query_name="match_documents",
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    async def add_document(self, user_id: str, content: str, metadata: dict = None):
        """Add a document to the vector store for a specific user."""
        try:
            # Enforce metadata
            metadata = metadata or {}
            metadata["user_id"] = user_id
            metadata["type"] = metadata.get("type", "generic")
            
            # Split text
            docs = self.text_splitter.create_documents([content], metadatas=[metadata])
            
            texts = [d.page_content for d in docs]
            metadatas = [d.metadata for d in docs]
            embeddings = self.embeddings.embed_documents(texts)
            
            data = []
            for i, text in enumerate(texts):
                data.append({
                    "content": text,
                    "metadata": metadatas[i],
                    "embedding": embeddings[i],
                    "user_id": user_id 
                })
            
            # Bulk insert
            self.client.table("documents").insert(data).execute()
            logger.info(f"Added {len(docs)} chunks for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise e

    async def sync_user_profile(self, user_id: str, profile_text: str):
        """
        Sync user profile text to RAG.
        Removes old profile document and adds new one.
        """
        try:
            # 1. Delete existing profile documents for this user
            # We assume metadata->type = 'profile'
            # But wait, looking at my generic match_documents, deleting by metadata requires different query.
            # OR we can just delete from 'documents' where user_id=X and metadata->>'type'='profile'
            
            self.client.table("documents") \
                .delete() \
                .eq("user_id", user_id) \
                .eq("metadata->>type", "profile") \
                .execute()
                
            # 2. Add new document
            await self.add_document(
                user_id=user_id, 
                content=profile_text, 
                metadata={"type": "profile", "source": "user_profile_service"}
            )
            logger.info(f"Synced profile for user {user_id} to RAG")
            return True
        except Exception as e:
            logger.error(f"Failed to sync profile for user {user_id}: {e}")
            # Don't raise, just log error so we don't block profile updates
            return False

    async def query(self, user_id: str, query_text: str, k: int = 4):
        """Query the vector store for a specific user."""
        try:
            # We use the native similarity_search but we need to pass the filter for the RPC function.
            # The `match_documents` function I defined takes `filter_user_id`.
            # `SupabaseVectorStore.similarity_search` calls the RPC.
            # It maps `query_embedding`, `match_threshold`, `match_count`.
            # It accepts `filter` argument which maps to `filter` parameter in RPC IF the RPC has it?
            
            # In my SQL, I named the parameter `filter_user_id`.
            # LangChain passes `filter` dict.
            # This mismatch prevents standard usage.
            
            # I should call the RPC manually using supabase client to ensure the parameter `filter_user_id` is passed correctly.
            
            query_embedding = self.embeddings.embed_query(query_text)
            
            params = {
                "query_embedding": query_embedding,
                "match_threshold": 0.5, # Configurable?
                "match_count": k,
                "filter_user_id": user_id
            }
            
            response = self.client.rpc("match_documents", params).execute()
            
            # Convert back to Documents? Or just return text
            results = []
            if response.data:
                for item in response.data:
                    results.append(item["content"]) # Return just content for now
            
            return results

        except Exception as e:
            logger.error(f"Failed to query RAG: {e}")
            return []

rag_service = RAGService()
