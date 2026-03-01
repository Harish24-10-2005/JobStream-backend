from abc import ABC, abstractmethod
from typing import Any

from src.core.config import settings
from src.core.logger import logger


class BaseAgent(ABC):
	"""
	Abstract base class for all JobAI agents.
	"""

	def __init__(self):
		self.settings = settings
		self.logger = logger

	@abstractmethod
	async def run(self, *args, **kwargs) -> Any:
		pass
