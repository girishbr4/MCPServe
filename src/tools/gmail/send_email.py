"""
send_email Tool
Composes and immediately sends an email via the Gmail API.

Input schema (per architecture.md §5.1):
  to      : string | string[]   — required
  subject : string              — required
  body    : string (plain/HTML) — required
  cc      : string | string[]   — optional
  bcc     : string | string[]   — optional
"""

import logging
from typing import Any

from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError, TransportError

from src.adapters.gmail_adapter import GmailAdapter
from src.auth.auth_manager import AuthManager
from src.errors.error_handler import (
    handle_google_api_error,
    handle_auth_error,
    handle_network_error,
    handle_unknown_error,
    validate_email_list,
    handle_invalid_recipient,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema — advertised to the MCP client via tools/list
# ---------------------------------------------------------------------------
TOOL_NAME = "send_email"
TOOL_DESCRIPTION = (
    "Compose and immediately send an email on behalf of the authenticated "
    "Google user. Supports plain text or HTML bodies, and optional CC/BCC."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ],
            "description": "Recipient email address or list of addresses.",
        },
        "subject": {
            "type": "string",
            "description": "Email subject line.",
        },
        "body": {
            "type": "string",
            "description": "Email body — plain text or HTML.",
        },
        "cc": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ],
            "description": "CC recipient(s). Optional.",
        },
        "bcc": {
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ],
            "description": "BCC recipient(s). Optional.",
        },
    },
    "required": ["to", "subject", "body"],
}


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def handle_send_email(auth_manager: AuthManager, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the send_email tool.

    Returns a ToolResult-compatible dict:
      • On success: {"content": [{"type": "text", "text": "..."}]}
      • On error:   {"isError": True, "content": [{"type": "text", "text": "ERROR [CODE]: ..."}]}
    """
    to: Any = arguments.get("to", "")
    subject: str = arguments.get("subject", "")
    body: str = arguments.get("body", "")
    cc: Any = arguments.get("cc")
    bcc: Any = arguments.get("bcc")

    # ── Normalize 'to' to a list for validation ───────────────────────────
    to_list = [to] if isinstance(to, str) else list(to)
    invalid = validate_email_list(to_list)
    if invalid:
        return handle_invalid_recipient(invalid[0])

    # ── Also validate cc / bcc if provided ───────────────────────────────
    if cc:
        cc_list = [cc] if isinstance(cc, str) else list(cc)
        invalid_cc = validate_email_list(cc_list)
        if invalid_cc:
            return handle_invalid_recipient(invalid_cc[0])

    if bcc:
        bcc_list = [bcc] if isinstance(bcc, str) else list(bcc)
        invalid_bcc = validate_email_list(bcc_list)
        if invalid_bcc:
            return handle_invalid_recipient(invalid_bcc[0])

    # ── Acquire credentials ──────────────────────────────────────────────
    try:
        creds = auth_manager.get_credentials()
    except RuntimeError as exc:
        return handle_auth_error(exc)

    # ── Call Gmail adapter ───────────────────────────────────────────────
    try:
        adapter = GmailAdapter(creds)
        result = adapter.send_message(to=to, subject=subject, body=body, cc=cc, bcc=bcc)
        message_id = result.get("id", "unknown")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Email sent successfully. Message ID: {message_id}",
                }
            ]
        }
    except HttpError as exc:
        return handle_google_api_error(exc, context="send_email")
    except TransportError as exc:
        return handle_network_error(exc)
    except Exception as exc:  # noqa: BLE001
        return handle_unknown_error(exc, context="send_email")
