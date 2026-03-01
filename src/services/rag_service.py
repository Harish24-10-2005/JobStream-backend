import logging

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import Client, create_client

from src.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
	def __init__(self):
		self.supabase_url = settings.supabase_url
		if settings.supabase_service_key:
			self.supabase_key = settings.supabase_service_key.get_secret_value()
		else:
			self.supabase_key = settings.supabase_anon_key

		self.client: Client = create_client(self.supabase_url, self.supabase_key)
		self.embeddings = None
		self.vector_store = None
		self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
		self.enabled = False

		# Lazy-safe initialization: avoid crashing app startup when GEMINI key is missing.
		self._init_embeddings()

	def _init_embeddings(self):
		try:
			if not settings.gemini_api_key:
				logger.warning('RAG embeddings disabled: GEMINI_API_KEY is not configured')
				self.enabled = False
				return
			self.embeddings = GoogleGenerativeAIEmbeddings(
				model=settings.gemini_embedding_model,
				google_api_key=settings.gemini_api_key.get_secret_value(),
			)
			self.vector_store = SupabaseVectorStore(
				client=self.client,
				embedding=self.embeddings,
				table_name='documents',
				query_name='match_documents',
			)
			self.enabled = True
		except Exception as e:
			self.enabled = False
			logger.warning(f'RAG embeddings initialization disabled: {e}')

	async def add_document(self, user_id: str, content: str, metadata: dict = None):
		"""Add a document to the vector store for a specific user."""
		if not self.enabled:
			logger.warning('RAG add_document skipped: RAG embeddings are disabled')
			return False
		try:
			# Enforce metadata
			metadata = metadata or {}
			metadata['user_id'] = user_id
			metadata['type'] = metadata.get('type', 'generic')

			# Split text
			docs = self.text_splitter.create_documents([content], metadatas=[metadata])

			texts = [d.page_content for d in docs]
			metadatas = [d.metadata for d in docs]
			embeddings = self.embeddings.embed_documents(texts)

			data = []
			for i, text in enumerate(texts):
				data.append({'content': text, 'metadata': metadatas[i], 'embedding': embeddings[i], 'user_id': user_id})

			# Bulk insert
			self.client.table('documents').insert(data).execute()
			logger.info(f'Added {len(docs)} chunks for user {user_id}')
			return True

		except Exception as e:
			logger.error(f'Failed to add document: {e}')
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

			self.client.table('documents').delete().eq('user_id', user_id).eq('metadata->>type', 'profile').execute()

			# 2. Add new document
			await self.add_document(
				user_id=user_id, content=profile_text, metadata={'type': 'profile', 'source': 'user_profile_service'}
			)
			logger.info(f'Synced profile for user {user_id} to RAG')
			return True
		except Exception as e:
			logger.error(f'Failed to sync profile for user {user_id}: {e}')
			# Don't raise, just log error so we don't block profile updates
			return False

	async def query(self, user_id: str, query_text: str, k: int = 4, limit: int = None):
		"""Query the vector store for a specific user."""
		if not self.enabled:
			logger.warning('RAG query skipped: RAG embeddings are disabled')
			return []
		try:
			effective_k = limit if isinstance(limit, int) and limit > 0 else k
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
				'query_embedding': query_embedding,
				'match_threshold': 0.5,  # Configurable?
				'match_count': effective_k,
				'filter_user_id': user_id,
			}

			response = self.client.rpc('match_documents', params).execute()

			# Convert back to Documents? Or just return text
			results = []
			if response.data:
				for item in response.data:
					results.append(
						{
							'content': item.get('content', ''),
							'metadata': item.get('metadata', {}),
							'similarity': item.get('similarity'),
						}
					)

			return results

		except Exception as e:
			logger.error(f'Failed to query RAG: {e}')
			return []


rag_service = RAGService()
