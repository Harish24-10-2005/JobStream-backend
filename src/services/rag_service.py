import logging
import asyncio
from typing import Any, Dict, Optional

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
		self.embedding_dim = settings.rag_embedding_dim
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

	def _normalize_embedding_dim(self, vector: Any) -> Optional[list[float]]:
		"""Ensure vectors match DB dimension to avoid insert/query failures."""
		if vector is None:
			return None
		try:
			values = [float(x) for x in vector]
		except Exception:
			return None

		current = len(values)
		target = int(self.embedding_dim or 768)
		if current == target:
			return values
		if current > target:
			logger.warning(f'RAG embedding dimension mismatch: got {current}, truncating to {target}')
			return values[:target]
		logger.warning(f'RAG embedding dimension mismatch: got {current}, padding to {target}')
		return values + [0.0] * (target - current)

	async def validate_startup_compatibility(self) -> tuple[bool, str]:
		"""
		Strict startup validation for production deploys.
		Checks:
		1) embedding model output dimension matches configured RAG_EMBEDDING_DIM
		2) configured dimension is accepted by database match_documents RPC
		"""
		if not self.enabled:
			return True, 'RAG disabled (no embedding provider configured)'

		try:
			probe_embedding = await asyncio.to_thread(self.embeddings.embed_query, 'rag startup compatibility check')
		except Exception as e:
			return False, f'Failed to generate embedding probe: {e}'

		probe_dim = len(probe_embedding or [])
		if probe_dim != self.embedding_dim:
			return (
				False,
				f'Embedding model produced {probe_dim} dimensions but RAG_EMBEDDING_DIM is {self.embedding_dim}. '
				f'Set RAG_EMBEDDING_DIM={probe_dim} or switch embedding model.',
			)

		zero_vec = [0.0] * self.embedding_dim
		params = {
			'query_embedding': zero_vec,
			'match_threshold': 0.0,
			'match_count': 1,
			'filter': {'user_id': '00000000-0000-0000-0000-000000000000'},
		}
		try:
			self.client.rpc('match_documents', params).execute()
		except Exception as rpc_err:
			# Backward compatibility path for legacy SQL signature.
			if 'filter_user_id' in str(rpc_err):
				try:
					self.client.rpc(
						'match_documents',
						{
							'query_embedding': zero_vec,
							'match_threshold': 0.0,
							'match_count': 1,
							'filter_user_id': '00000000-0000-0000-0000-000000000000',
						},
					).execute()
				except Exception as legacy_err:
					return False, f'RAG RPC startup check failed (legacy signature): {legacy_err}'
			else:
				return False, f'RAG RPC startup check failed: {rpc_err}'

		return True, 'RAG startup compatibility check passed'

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
			embeddings = await asyncio.to_thread(self.embeddings.embed_documents, texts)

			data = []
			for i, text in enumerate(texts):
				data.append({
					'content': text,
					'metadata': metadatas[i],
					'embedding': self._normalize_embedding_dim(embeddings[i]),
					'user_id': user_id,
				})

			# Bulk insert
			self.client.table('documents').insert(data).execute()
			logger.info(f'Added {len(docs)} chunks for user {user_id}')
			return True

		except Exception as e:
			logger.error(f'Failed to add document: {e}')
			raise e

	async def delete_documents(self, user_id: str, doc_type: Optional[str] = None, metadata_match: Optional[Dict[str, Any]] = None):
		"""Delete RAG documents for a user, optionally filtered by type/metadata."""
		try:
			query = self.client.table('documents').delete().eq('user_id', user_id)
			if doc_type:
				query = query.contains('metadata', {'type': doc_type})
			if metadata_match:
				query = query.contains('metadata', metadata_match)
			query.execute()
			return True
		except Exception as e:
			logger.warning(f'Failed to delete RAG documents for {user_id}: {e}')
			return False

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

			await self.delete_documents(user_id=user_id, doc_type='profile')

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

	async def sync_resume_document(self, user_id: str, resume_id: str, content: str, name: str = ''):
		"""Replace resume RAG chunks for a resume id with fresh content."""
		try:
			await self.delete_documents(user_id=user_id, doc_type='resume', metadata_match={'resume_id': resume_id})
			await self.add_document(
				user_id=user_id,
				content=content,
				metadata={'type': 'resume', 'resume_id': resume_id, 'name': name},
			)
			return True
		except Exception as e:
			logger.warning(f'Failed to sync resume document for {user_id}/{resume_id}: {e}')
			return False

	async def query(self, user_id: str, query_text: str, k: int = 4, limit: int = None):
		"""Query the vector store for a specific user."""
		if not self.enabled:
			logger.warning('RAG query skipped: RAG embeddings are disabled')
			return []
		try:
			effective_k = limit if isinstance(limit, int) and limit > 0 else k
			# Call RPC manually to enforce user-scoped retrieval and support both:
			# 1) current SQL signature: match_documents(..., filter jsonb)
			# 2) legacy SQL signature:  match_documents(..., filter_user_id uuid)

			query_embedding = await asyncio.to_thread(self.embeddings.embed_query, query_text)
			query_embedding = self._normalize_embedding_dim(query_embedding)
			if not query_embedding:
				logger.error('Failed to normalize query embedding')
				return []
			params = {
				'query_embedding': query_embedding,
				'match_threshold': 0.5,  # Configurable?
				'match_count': effective_k,
				'filter': {'user_id': user_id},
			}

			try:
				response = self.client.rpc('match_documents', params).execute()
			except Exception as rpc_err:
				# Backward compatibility for older SQL function signatures.
				if 'filter_user_id' in str(rpc_err):
					legacy_params = {
						'query_embedding': query_embedding,
						'match_threshold': 0.5,
						'match_count': effective_k,
						'filter_user_id': user_id,
					}
					response = self.client.rpc('match_documents', legacy_params).execute()
				else:
					raise

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
