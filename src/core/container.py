"""
Dependency Injection Container — Lightweight DI for Production AI

Provides a singleton-scoped container for managing service lifetimes.
Follows the Register → Resolve pattern, supporting:
  - Singleton instances (one per container lifetime)
  - Factory functions (new instance each time)
  - Lazy initialization (deferred until first resolve)

Architecture:
  FastAPI depends() → Container.resolve() → Service

Usage:
    from src.core.container import container, inject

    # Registration (at startup)
    container.register_singleton("llm", LLMProvider)
    container.register_factory("rag", lambda: RAGService(container.resolve("llm")))

    # Resolution (in routes)
    @router.get("/search")
    async def search(rag: RAGService = Depends(inject("rag"))):
        return await rag.search(...)
"""

import logging
from typing import Any, Callable, Dict, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LifecycleScope:
	SINGLETON = 'singleton'
	FACTORY = 'factory'


class ServiceRegistration:
	"""Holds the registration metadata for a service."""

	__slots__ = ('name', 'factory', 'scope', 'instance', 'initialized')

	def __init__(self, name: str, factory: Callable, scope: str):
		self.name = name
		self.factory = factory
		self.scope = scope
		self.instance: Any = None
		self.initialized = False


class Container:
	"""
	Lightweight DI container with singleton and factory scopes.

	Thread-safe for read-heavy workloads (registrations happen at startup,
	resolutions happen at request time).
	"""

	def __init__(self):
		self._registrations: Dict[str, ServiceRegistration] = {}
		self._overrides: Dict[str, Any] = {}  # For testing

	# ─── Registration ─────────────────────────────────────────

	def register_singleton(self, name: str, factory_or_class: Union[Callable, Type], *args, **kwargs) -> 'Container':
		"""
		Register a singleton service. The factory is called once,
		and the result is cached for all subsequent resolves.
		"""
		if args or kwargs:
			original = factory_or_class
			factory = lambda: original(*args, **kwargs)
		else:
			factory = factory_or_class

		self._registrations[name] = ServiceRegistration(name=name, factory=factory, scope=LifecycleScope.SINGLETON)
		logger.debug(f'[DI] Registered singleton: {name}')
		return self

	def register_factory(
		self,
		name: str,
		factory: Callable,
	) -> 'Container':
		"""
		Register a factory service. The factory is called on every resolve.
		"""
		self._registrations[name] = ServiceRegistration(name=name, factory=factory, scope=LifecycleScope.FACTORY)
		logger.debug(f'[DI] Registered factory: {name}')
		return self

	def register_instance(self, name: str, instance: Any) -> 'Container':
		"""
		Register an already-constructed instance as a singleton.
		"""
		reg = ServiceRegistration(name=name, factory=lambda: instance, scope=LifecycleScope.SINGLETON)
		reg.instance = instance
		reg.initialized = True
		self._registrations[name] = reg
		logger.debug(f'[DI] Registered instance: {name}')
		return self

	# ─── Resolution ───────────────────────────────────────────

	def resolve(self, name: str) -> Any:
		"""
		Resolve a service by name.

		For singletons: returns cached instance (lazy-init on first call).
		For factories: creates new instance each call.

		Raises KeyError if service is not registered.
		"""
		# Check overrides first (for testing)
		if name in self._overrides:
			return self._overrides[name]

		if name not in self._registrations:
			raise KeyError(f"Service '{name}' not registered. Available: {list(self._registrations.keys())}")

		reg = self._registrations[name]

		if reg.scope == LifecycleScope.SINGLETON:
			if not reg.initialized:
				try:
					reg.instance = reg.factory()
					reg.initialized = True
					logger.debug(f'[DI] Initialized singleton: {name}')
				except Exception as e:
					logger.error(f'[DI] Failed to initialize {name}: {e}')
					raise
			return reg.instance

		elif reg.scope == LifecycleScope.FACTORY:
			return reg.factory()

	def has(self, name: str) -> bool:
		"""Check if a service is registered."""
		return name in self._registrations

	# ─── Testing Support ─────────────────────────────────────

	def override(self, name: str, instance: Any) -> 'Container':
		"""Override a registration with a mock/test instance."""
		self._overrides[name] = instance
		return self

	def clear_overrides(self):
		"""Remove all test overrides."""
		self._overrides.clear()

	def reset(self):
		"""Reset all registrations and overrides (for testing)."""
		self._registrations.clear()
		self._overrides.clear()

	# ─── Diagnostics ─────────────────────────────────────────

	@property
	def registered_services(self) -> list:
		"""List all registered service names."""
		return list(self._registrations.keys())

	def health_check(self) -> Dict[str, str]:
		"""Check initialization status of all services."""
		return {name: 'initialized' if reg.initialized else 'pending' for name, reg in self._registrations.items()}


# ─── Singleton Container ─────────────────────────────────────

container = Container()


# ─── FastAPI DI Bridge ────────────────────────────────────────


def inject(name: str) -> Callable:
	"""
	FastAPI Depends() bridge for the DI container.

	Usage:
	    @router.get("/")
	    async def index(svc: MyService = Depends(inject("my_service"))):
	        ...
	"""

	def _resolver():
		return container.resolve(name)

	return _resolver
