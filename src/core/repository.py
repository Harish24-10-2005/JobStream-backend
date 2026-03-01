"""
Repository Pattern — Clean Data Access Abstraction Layer

Provides a generic repository interface that decouples business logic
from storage implementation (Supabase, PostgreSQL, in-memory).

Patterns implemented:
  - Repository pattern (CRUD abstraction)
  - Unit of Work (transactional boundaries)
  - Specification pattern (composable query filters)

Usage:
    from src.core.repository import SupabaseRepository

    class JobRepository(SupabaseRepository):
        table_name = "jobs"

    repo = JobRepository(client)
    job = await repo.get_by_id("uuid")
    jobs = await repo.find({"status": "active"}, limit=10)
    await repo.create({"title": "SDE-2", "company": "Google"})
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ─── Specification Pattern ──────────────────────────────────────


class Specification:
	"""
	Composable query filter for the Repository pattern.

	Supports:
	  - eq, neq, gt, gte, lt, lte comparisons
	  - in_, like, ilike text matching
	  - AND/OR composition
	"""

	def __init__(self):
		self._filters: List[Dict[str, Any]] = []

	def eq(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'eq', 'field': field, 'value': value})
		return self

	def neq(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'neq', 'field': field, 'value': value})
		return self

	def gt(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'gt', 'field': field, 'value': value})
		return self

	def gte(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'gte', 'field': field, 'value': value})
		return self

	def lt(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'lt', 'field': field, 'value': value})
		return self

	def lte(self, field: str, value: Any) -> 'Specification':
		self._filters.append({'op': 'lte', 'field': field, 'value': value})
		return self

	def in_(self, field: str, values: List[Any]) -> 'Specification':
		self._filters.append({'op': 'in', 'field': field, 'value': values})
		return self

	def like(self, field: str, pattern: str) -> 'Specification':
		self._filters.append({'op': 'like', 'field': field, 'value': pattern})
		return self

	def ilike(self, field: str, pattern: str) -> 'Specification':
		self._filters.append({'op': 'ilike', 'field': field, 'value': pattern})
		return self

	@property
	def filters(self) -> List[Dict[str, Any]]:
		return self._filters


# ─── Abstract Repository ───────────────────────────────────────


class BaseRepository(ABC, Generic[T]):
	"""
	Abstract repository interface defining standard data operations.
	All concrete repositories must implement these methods.
	"""

	@abstractmethod
	async def get_by_id(self, id: str) -> Optional[T]:
		"""Fetch a single record by primary key."""
		pass

	@abstractmethod
	async def find(
		self,
		filters: Dict[str, Any] = None,
		spec: Specification = None,
		limit: int = 100,
		offset: int = 0,
		order_by: str = None,
		ascending: bool = True,
	) -> List[T]:
		"""Query records with optional filters and pagination."""
		pass

	@abstractmethod
	async def create(self, data: Dict[str, Any]) -> T:
		"""Insert a new record."""
		pass

	@abstractmethod
	async def update(self, id: str, data: Dict[str, Any]) -> Optional[T]:
		"""Update an existing record."""
		pass

	@abstractmethod
	async def delete(self, id: str) -> bool:
		"""Delete a record by primary key."""
		pass

	@abstractmethod
	async def count(self, filters: Dict[str, Any] = None) -> int:
		"""Count records matching optional filters."""
		pass


# ─── Supabase Repository ───────────────────────────────────────


class SupabaseRepository(BaseRepository[Dict[str, Any]]):
	"""
	Concrete repository backed by Supabase (PostgREST).

	Translates Specification filters to Supabase query methods.
	Includes soft-delete support and automatic timestamp management.
	"""

	table_name: str = ''
	soft_delete: bool = False  # If True, sets deleted_at instead of hard delete

	def __init__(self, client: Any):
		"""
		Args:
		    client: Supabase client instance
		"""
		if not self.table_name:
			raise ValueError(f'{self.__class__.__name__} must define table_name')
		self._client = client

	def _table(self):
		"""Get the table query builder."""
		return self._client.table(self.table_name)

	def _apply_spec(self, query, spec: Specification):
		"""Apply Specification filters to a Supabase query."""
		for f in spec.filters:
			op, field, value = f['op'], f['field'], f['value']
			if op == 'eq':
				query = query.eq(field, value)
			elif op == 'neq':
				query = query.neq(field, value)
			elif op == 'gt':
				query = query.gt(field, value)
			elif op == 'gte':
				query = query.gte(field, value)
			elif op == 'lt':
				query = query.lt(field, value)
			elif op == 'lte':
				query = query.lte(field, value)
			elif op == 'in':
				query = query.in_(field, value)
			elif op == 'like':
				query = query.like(field, value)
			elif op == 'ilike':
				query = query.ilike(field, value)
		return query

	async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
		try:
			result = self._table().select('*').eq('id', id).maybe_single().execute()
			return result.data if result.data else None
		except Exception as e:
			logger.error(f'[{self.table_name}] get_by_id error: {e}')
			return None

	async def find(
		self,
		filters: Dict[str, Any] = None,
		spec: Specification = None,
		limit: int = 100,
		offset: int = 0,
		order_by: str = None,
		ascending: bool = True,
	) -> List[Dict[str, Any]]:
		try:
			query = self._table().select('*')

			# Apply dict filters
			if filters:
				for key, value in filters.items():
					query = query.eq(key, value)

			# Apply specification
			if spec:
				query = self._apply_spec(query, spec)

			# Exclude soft-deleted records
			if self.soft_delete:
				query = query.is_('deleted_at', 'null')

			# Ordering
			if order_by:
				query = query.order(order_by, desc=not ascending)

			# Pagination
			query = query.range(offset, offset + limit - 1)

			result = query.execute()
			return result.data or []
		except Exception as e:
			logger.error(f'[{self.table_name}] find error: {e}')
			return []

	async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		try:
			data['created_at'] = datetime.now(timezone.utc).isoformat()
			result = self._table().insert(data).execute()
			return result.data[0] if result.data else None
		except Exception as e:
			logger.error(f'[{self.table_name}] create error: {e}')
			return None

	async def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		try:
			data['updated_at'] = datetime.now(timezone.utc).isoformat()
			result = self._table().update(data).eq('id', id).execute()
			return result.data[0] if result.data else None
		except Exception as e:
			logger.error(f'[{self.table_name}] update error: {e}')
			return None

	async def delete(self, id: str) -> bool:
		try:
			if self.soft_delete:
				self._table().update({'deleted_at': datetime.now(timezone.utc).isoformat()}).eq('id', id).execute()
			else:
				self._table().delete().eq('id', id).execute()
			return True
		except Exception as e:
			logger.error(f'[{self.table_name}] delete error: {e}')
			return False

	async def count(self, filters: Dict[str, Any] = None) -> int:
		try:
			query = self._table().select('*', count='exact')
			if filters:
				for key, value in filters.items():
					query = query.eq(key, value)
			if self.soft_delete:
				query = query.is_('deleted_at', 'null')
			result = query.execute()
			return result.count or 0
		except Exception as e:
			logger.error(f'[{self.table_name}] count error: {e}')
			return 0

	async def upsert(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		"""Insert or update based on primary key."""
		try:
			data['updated_at'] = datetime.now(timezone.utc).isoformat()
			result = self._table().upsert(data).execute()
			return result.data[0] if result.data else None
		except Exception as e:
			logger.error(f'[{self.table_name}] upsert error: {e}')
			return None


# ─── In-Memory Repository (for testing) ───────────────────────


class InMemoryRepository(BaseRepository[Dict[str, Any]]):
	"""In-memory repository for unit testing without database."""

	def __init__(self):
		self._store: Dict[str, Dict[str, Any]] = {}
		self._counter = 0

	async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
		return self._store.get(id)

	async def find(
		self,
		filters: Dict[str, Any] = None,
		spec: Specification = None,
		limit: int = 100,
		offset: int = 0,
		order_by: str = None,
		ascending: bool = True,
	) -> List[Dict[str, Any]]:
		items = list(self._store.values())

		if filters:
			items = [item for item in items if all(item.get(k) == v for k, v in filters.items())]

		if order_by:
			items = sorted(
				items,
				key=lambda x: x.get(order_by, ''),
				reverse=not ascending,
			)

		return items[offset : offset + limit]

	async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
		self._counter += 1
		if 'id' not in data:
			data['id'] = f'mem_{self._counter}'
		data['created_at'] = datetime.now(timezone.utc).isoformat()
		self._store[data['id']] = data
		return data

	async def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
		if id not in self._store:
			return None
		data['updated_at'] = datetime.now(timezone.utc).isoformat()
		self._store[id].update(data)
		return self._store[id]

	async def delete(self, id: str) -> bool:
		if id in self._store:
			del self._store[id]
			return True
		return False

	async def count(self, filters: Dict[str, Any] = None) -> int:
		if not filters:
			return len(self._store)
		return len(await self.find(filters=filters))
