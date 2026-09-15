"""
draft_email Tool
Saves a composed email as a Gmail draft for human review before sending.

Input schema (per architecture.md §5.2):
  to      : string | string[]   — required
  subject : string              — required
  body    : string (plain/HTML) — required
"""

import logging
from typing import Any

from googleapiclient.errors import HttpError
from google.auth.exceptions import TransportError

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
TOOL_NAME = "draft_email"
TOOL_DESCRIPTION = (
    "Save a composed email as a Gmail draft for human review before sending. "
    "The draft will appear in the authenticated user's Gmail Drafts folder."
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
    },
    "required": ["to", "subject", "body"],
}


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def handle_draft_email(auth_manager: AuthManager, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the draft_email tool.

    Returns a ToolResult-compatible dict:
      • On success: {"content": [{"type": "text", "text": "..."}]}
      • On error:   {"isError": True, "content": [{"type": "text", "text": "ERROR [CODE]: ..."}]}
    """
    to: Any = arguments.get("to", "")
    subject: str = arguments.get("subject", "")
    body: str = arguments.get("body", "")

    # ── Validate recipient addresses ─────────────────────────────────────
    to_list = [to] if isinstance(to, str) else list(to)
    invalid = validate_email_list(to_list)
    if invalid:
        return handle_invalid_recipient(invalid[0])

    # ── Acquire credentials ──────────────────────────────────────────────
    try:
        creds = auth_manager.get_credentials()
    except RuntimeError as exc:
        return handle_auth_error(exc)

    # ── Call Gmail adapter ───────────────────────────────────────────────
    try:
        adapter = GmailAdapter(creds)
        result = adapter.create_draft(to=to, subject=subject, body=body)
        draft_id = result.get("id", "unknown")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Draft created successfully. Draft ID: {draft_id}",
                }
            ]
        }
    except HttpError as exc:
        return handle_google_api_error(exc, context="draft_email")
    except TransportError as exc:
        return handle_network_error(exc)
    except Exception as exc:  # noqa: BLE001
        return handle_unknown_error(exc, context="draft_email")
