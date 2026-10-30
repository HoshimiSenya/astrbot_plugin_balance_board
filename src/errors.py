"""Typed errors shared by the HTTP client and the message formatters."""

from __future__ import annotations


class BalanceError(Exception):
    """Base class for errors that can be shown to the user."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "",
        status: int = 0,
        retryable: bool = False,
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.retryable = retryable
        self.hint = hint


class AuthError(BalanceError):
    """The API key is invalid or lacks permission."""


class RateLimitError(BalanceError):
    """The provider asked us to slow down."""


class NetworkError(BalanceError):
    """Timeout, DNS failure or connection reset."""


class UpstreamError(BalanceError):
    """The provider returned an unexpected response."""


class UnsupportedError(BalanceError):
    """The provider removed or never offered the balance endpoint."""
