"""
Data models and constants for the LiveApplier service.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ApplierStatus(str, Enum):
	"""Status states for the Live Applier service."""

	IDLE = 'idle'
	INITIALIZING = 'initializing'
	RUNNING = 'running'
	WAITING_HITL = 'waiting_hitl'  # Waiting for human input
	WAITING_DRAFT = 'waiting_draft'  # Waiting for draft confirmation
	COMPLETED = 'completed'
	FAILED = 'failed'
	CANCELLED = 'cancelled'


@dataclass
class ApplierResult:
	"""Result of a job application attempt."""

	success: bool
	status: ApplierStatus
	url: str
	message: str = ''
	error: Optional[str] = None
	proof_screenshot: Optional[str] = None  # Base64 encoded
	application_id: Optional[str] = None  # Tracking ID from ATS
	duration_seconds: float = 0.0
	metadata: Dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> Dict[str, Any]:
		"""Convert to dictionary for JSON serialization."""
		return {
			'success': self.success,
			'status': self.status.value,
			'url': self.url,
			'message': self.message,
			'error': self.error,
			'proof_screenshot': self.proof_screenshot,
			'application_id': self.application_id,
			'duration_seconds': self.duration_seconds,
			'metadata': self.metadata,
		}


# ============================================================================
# Constants
# ============================================================================


class Timeouts:
	"""Timeout constants in seconds."""

	HITL_RESPONSE = 120  # 2 minutes for human input
	DRAFT_REVIEW = 300  # 5 minutes for draft confirmation
	PAGE_LOAD = 30  # Page navigation timeout
	ELEMENT_WAIT = 10  # Element detection timeout
	SCREENSHOT = 5  # Screenshot capture timeout
	LLM_RETRY_BASE = 5  # Base wait for LLM retry (exponential)


class ScreenshotConfig:
	"""Screenshot streaming configuration."""

	FPS = 5  # Frames per second
	INTERVAL = 0.2  # Seconds between frames (1/FPS)
	FORMAT = 'jpeg'
	QUALITY = 50  # JPEG quality (0-100)
	DRAFT_QUALITY = 80  # Higher quality for draft review
	FULL_PAGE = False  # Viewport only for streaming
	DRAFT_FULL_PAGE = True  # Full page for draft review


class AgentConfig:
	"""Browser-use agent configuration."""

	MAX_FAILURES = 5  # Max retry attempts for agent
	USE_VISION = False  # Use DOM-based (more reliable)
	MAX_LLM_RETRIES = 3  # LLM retry count
	TEMPERATURE = 0.6  # LLM temperature


class BrowserArgs:
	"""Chrome browser arguments for Docker/production."""

	DOCKER_ARGS = [
		'--disable-dev-shm-usage',  # Overcome limited /dev/shm in containers
		'--disable-gpu',  # Disable GPU in headless
		'--single-process',  # Reduce memory in containers
		'--no-sandbox',  # Required in Docker
	]
