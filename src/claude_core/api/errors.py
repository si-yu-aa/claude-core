"""API error types."""

from dataclasses import dataclass
from typing import Optional, Any

class APIError(Exception):
    """Base API error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        body: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body

    def __str__(self) -> str:
        if self.status_code:
            return f"APIError({self.status_code}): {self.message}"
        return f"APIError: {self.message}"

class RateLimitError(APIError):
    """Rate limit exceeded error."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after

class AuthenticationError(APIError):
    """Authentication error."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)

class InvalidRequestError(APIError):
    """Invalid request error."""

    def __init__(self, message: str, body: Optional[dict] = None):
        super().__init__(message, status_code=400, body=body)

class APIConnectionError(APIError):
    """Connection error."""

    def __init__(self, message: str = "Connection failed"):
        super().__init__(message)

def is_retryable_error(error: APIError) -> bool:
    """Check if an error is retryable."""
    if isinstance(error, RateLimitError):
        return True
    if error.status_code and error.status_code >= 500:
        return True
    return False