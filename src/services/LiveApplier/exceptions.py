"""
Custom exceptions for the LiveApplier service.

Provides specific exception types for better error handling and debugging.
"""


class LiveApplierError(Exception):
    """Base exception for all LiveApplier errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ProfileNotFoundError(LiveApplierError):
    """Raised when user profile cannot be loaded."""
    
    def __init__(self, user_id: str, message: str = None):
        super().__init__(
            message or f"Profile not found for user: {user_id}",
            details={"user_id": user_id}
        )
        self.user_id = user_id


class BrowserConnectionError(LiveApplierError):
    """Raised when browser fails to initialize or loses connection."""
    
    def __init__(self, message: str = "Browser connection failed", reason: str = None):
        super().__init__(message, details={"reason": reason})
        self.reason = reason


class LLMUnavailableError(LiveApplierError):
    """Raised when no LLM provider is available (all failed or missing keys)."""
    
    def __init__(self, attempted_providers: list = None):
        providers = attempted_providers or []
        super().__init__(
            f"No LLM available. Attempted: {', '.join(providers) or 'None'}",
            details={"attempted_providers": providers}
        )
        self.attempted_providers = providers


class HITLTimeoutError(LiveApplierError):
    """Raised when Human-in-the-Loop response times out."""
    
    def __init__(self, hitl_id: str, timeout_seconds: float):
        super().__init__(
            f"HITL request '{hitl_id}' timed out after {timeout_seconds}s",
            details={"hitl_id": hitl_id, "timeout_seconds": timeout_seconds}
        )
        self.hitl_id = hitl_id
        self.timeout_seconds = timeout_seconds


class FormFillingError(LiveApplierError):
    """Raised when a form field cannot be filled after retries."""
    
    def __init__(self, field_name: str, attempts: int, reason: str = None):
        super().__init__(
            f"Failed to fill field '{field_name}' after {attempts} attempts",
            details={"field_name": field_name, "attempts": attempts, "reason": reason}
        )
        self.field_name = field_name
        self.attempts = attempts


class NavigationError(LiveApplierError):
    """Raised when page navigation fails."""
    
    def __init__(self, url: str, reason: str = None):
        super().__init__(
            f"Failed to navigate to: {url}",
            details={"url": url, "reason": reason}
        )
        self.url = url
