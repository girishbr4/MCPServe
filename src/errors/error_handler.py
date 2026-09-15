"""
Error Handler
Centralized mapping of exceptions to structured, agent-readable MCP error responses.

All errors returned to the agent follow this envelope:
  {
    "isError": True,
    "content": [{"type": "text", "text": "ERROR [CODE]: <descriptive message>"}]
  }

Errors are NON-FATAL at the tool level — the server stays alive after any error.
"""

import logging
import re
from typing import Any

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------
class ErrorCode:
    AUTH_EXPIRED = "AUTH_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    INVALID_DOCUMENT_ID = "INVALID_DOCUMENT_ID"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# ---------------------------------------------------------------------------
# Helper: build a ToolResult-compatible error dict
# ---------------------------------------------------------------------------
def make_error_result(code: str, message: str) -> dict[str, Any]:
    """
    Build a structured MCP ToolResult error that the SDK will serialize
    correctly back to the calling agent.
    """
    full_text = f"ERROR [{code}]: {message}"
    logger.error("TOOL ERROR — %s", full_text)
    return {
        "isError": True,
        "content": [{"type": "text", "text": full_text}],
    }


# ---------------------------------------------------------------------------
# Google API HttpError classifier
# ---------------------------------------------------------------------------
def handle_google_api_error(exc: HttpError, context: str = "") -> dict[str, Any]:
    """
    Translate a googleapiclient.errors.HttpError into a structured error result.

    Args:
        exc:     The HttpError raised by the Google API client.
        context: Optional context string (e.g., "send_email") for richer logging.
    """
    status = exc.resp.status if exc.resp else 0
    reason = _extract_reason(exc)
    ctx = f" ({context})" if context else ""

    if status == 401:
        return make_error_result(
            ErrorCode.AUTH_EXPIRED,
            "Authentication Expired: Please re-authorize the server with Google."
            + ctx,
        )
    if status == 403:
        return make_error_result(
            ErrorCode.INSUFFICIENT_PERMISSIONS,
            f"Insufficient Permissions: Ensure the OAuth scope includes Gmail Send "
            f"and Docs Edit access. Detail: {reason}{ctx}",
        )
    if status == 404:
        # Context tells us whether it's a doc or a message
        if "document" in context.lower() or "doc" in context.lower():
            return make_error_result(
                ErrorCode.INVALID_DOCUMENT_ID,
                "Invalid Document ID: The provided document_id does not correspond "
                "to an accessible Google Doc. Check the ID from the document URL."
                + ctx,
            )
        return make_error_result(
            ErrorCode.UNKNOWN_ERROR,
            f"Resource not found (404). Detail: {reason}{ctx}",
        )
    if status == 429:
        return make_error_result(
            ErrorCode.RATE_LIMITED,
            "Rate Limited: Google API quota exceeded. Retry after a short delay." + ctx,
        )
    if status >= 500:
        return make_error_result(
            ErrorCode.NETWORK_ERROR,
            f"Google API server error ({status}). Retry after a moment. Detail: {reason}{ctx}",
        )

    return make_error_result(
        ErrorCode.UNKNOWN_ERROR,
        f"Google API error (HTTP {status}). Detail: {reason}{ctx}",
    )


def handle_auth_error(exc: Exception) -> dict[str, Any]:
    """Handle errors raised by the AuthManager."""
    msg = str(exc)
    if "AUTH_EXPIRED" in msg or "refresh" in msg.lower():
        return make_error_result(
            ErrorCode.AUTH_EXPIRED,
            "Authentication Expired: Please re-authorize the server with Google.",
        )
    return make_error_result(
        ErrorCode.UNKNOWN_ERROR,
        f"Authentication error: {msg}",
    )


def handle_network_error(exc: Exception) -> dict[str, Any]:
    """Handle connectivity/transport errors."""
    return make_error_result(
        ErrorCode.NETWORK_ERROR,
        f"Network Error: Could not reach Google APIs. Check server connectivity. "
        f"Detail: {exc}",
    )


def handle_invalid_recipient(address: str) -> dict[str, Any]:
    """Return a validation error for malformed email addresses."""
    return make_error_result(
        ErrorCode.INVALID_RECIPIENT,
        f"Invalid Recipient: The address '{address}' is not a valid email address.",
    )


def handle_unknown_error(exc: Exception, context: str = "") -> dict[str, Any]:
    """Catch-all for unexpected exceptions."""
    ctx = f" ({context})" if context else ""
    return make_error_result(
        ErrorCode.UNKNOWN_ERROR,
        f"Unknown Error: An unexpected error occurred{ctx}. Detail: {exc}",
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(address: str) -> bool:
    """Simple RFC-5321 surface-level email validation."""
    return bool(_EMAIL_RE.match(address.strip()))


def validate_email_list(addresses: list[str]) -> list[str]:
    """Return a list of invalid addresses from the input list."""
    return [a for a in addresses if not validate_email(a)]


def _extract_reason(exc: HttpError) -> str:
    """Safely extract a human-readable reason from an HttpError."""
    try:
        import json as _json
        detail = _json.loads(exc.content)
        return detail.get("error", {}).get("message", str(exc))
    except Exception:
        return str(exc)
