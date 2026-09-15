"""
append_to_doc Tool
Appends text content to the end of an existing Google Document.

Input schema (per architecture.md §5.3):
  document_id : string — required (the ID from the Google Doc URL)
  content     : string — required (the text to append)
"""

import logging
from typing import Any

from googleapiclient.errors import HttpError
from google.auth.exceptions import TransportError

from src.adapters.docs_adapter import DocsAdapter
from src.auth.auth_manager import AuthManager
from src.errors.error_handler import (
    handle_google_api_error,
    handle_auth_error,
    handle_network_error,
    handle_unknown_error,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema — advertised to the MCP client via tools/list
# ---------------------------------------------------------------------------
TOOL_NAME = "append_to_doc"
TOOL_DESCRIPTION = (
    "Append text content to the end of an existing Google Document. "
    "Provide the document ID from the Doc's URL and the text to insert."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_id": {
            "type": "string",
            "description": (
                "The Google Doc ID — the long alphanumeric string in the document URL "
                "(e.g., '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms')."
            ),
        },
        "content": {
            "type": "string",
            "description": "The text content to append to the end of the document.",
        },
    },
    "required": ["document_id", "content"],
}


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def handle_append_to_doc(auth_manager: AuthManager, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the append_to_doc tool.

    Returns a ToolResult-compatible dict:
      • On success: {"content": [{"type": "text", "text": "..."}]}
      • On error:   {"isError": True, "content": [{"type": "text", "text": "ERROR [CODE]: ..."}]}
    """
    document_id: str = arguments.get("document_id", "").strip()
    content: str = arguments.get("content", "")

    # ── Basic input validation ───────────────────────────────────────────
    if not document_id:
        from src.errors.error_handler import make_error_result, ErrorCode
        return make_error_result(
            ErrorCode.INVALID_DOCUMENT_ID,
            "Invalid Document ID: 'document_id' parameter is empty. "
            "Provide the alphanumeric ID from the Google Doc URL.",
        )

    if not content:
        from src.errors.error_handler import make_error_result, ErrorCode
        return make_error_result(
            ErrorCode.UNKNOWN_ERROR,
            "Content to append is empty. Provide a non-empty 'content' string.",
        )

    # ── Acquire credentials ──────────────────────────────────────────────
    try:
        creds = auth_manager.get_credentials()
    except RuntimeError as exc:
        return handle_auth_error(exc)

    # ── Call Docs adapter ────────────────────────────────────────────────
    try:
        adapter = DocsAdapter(creds)
        adapter.append_text(document_id=document_id, content=content)
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Content appended successfully to document {document_id}."
                    ),
                }
            ]
        }
    except HttpError as exc:
        return handle_google_api_error(exc, context="append_to_doc document")
    except TransportError as exc:
        return handle_network_error(exc)
    except ValueError as exc:
        from src.errors.error_handler import make_error_result, ErrorCode
        return make_error_result(ErrorCode.INVALID_DOCUMENT_ID, str(exc))
    except Exception as exc:  # noqa: BLE001
        return handle_unknown_error(exc, context="append_to_doc")
