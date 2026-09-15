"""
Tool Registry
Central registry that wires tool modules to the FastMCP instance (MCP SDK v2).

Each tool is registered via the @server.tool() decorator with explicit
name, description, and a typed async wrapper that calls the sync handler.
"""

import logging
from typing import Any, Optional, Union

from mcp.server.mcpserver import MCPServer

from src.auth.auth_manager import AuthManager
from src.tools.gmail.send_email import handle_send_email
from src.tools.gmail.draft_email import handle_draft_email
from src.tools.docs.append_to_doc import handle_append_to_doc

logger = logging.getLogger(__name__)


def register_all_tools(server: MCPServer, auth_manager: AuthManager) -> None:
    """
    Register all three tools with the FastMCP instance using the v2 @tool decorator.
    Each tool is a typed async function; the SDK infers the JSON schema from type hints.
    """

    # ── send_email ────────────────────────────────────────────────────────────

    @server.tool(
        name="send_email",
        description=(
            "Compose and immediately send an email on behalf of the authenticated "
            "Google user. Supports plain text or HTML bodies, and optional CC/BCC."
        ),
    )
    async def send_email(
        to: Union[str, list[str]],
        subject: str,
        body: str,
        cc: Optional[Union[str, list[str]]] = None,
        bcc: Optional[Union[str, list[str]]] = None,
    ) -> str:
        """Send an email via Gmail API."""
        logger.info("TOOL: send_email called")
        result = handle_send_email(auth_manager, {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc,
            "bcc": bcc,
        })
        return result["content"][0]["text"]

    # ── draft_email ───────────────────────────────────────────────────────────

    @server.tool(
        name="draft_email",
        description=(
            "Save a composed email as a Gmail draft for human review before sending. "
            "The draft will appear in the authenticated user's Gmail Drafts folder."
        ),
    )
    async def draft_email(
        to: Union[str, list[str]],
        subject: str,
        body: str,
    ) -> str:
        """Save an email as a Gmail draft."""
        logger.info("TOOL: draft_email called")
        result = handle_draft_email(auth_manager, {
            "to": to,
            "subject": subject,
            "body": body,
        })
        return result["content"][0]["text"]

    # ── append_to_doc ─────────────────────────────────────────────────────────

    @server.tool(
        name="append_to_doc",
        description=(
            "Append text content to the end of an existing Google Document. "
            "Provide the document ID from the Doc's URL and the text to insert."
        ),
    )
    async def append_to_doc(
        document_id: str,
        content: str,
    ) -> str:
        """Append text to an existing Google Document."""
        logger.info("TOOL: append_to_doc called, doc_id=%s", document_id)
        result = handle_append_to_doc(auth_manager, {
            "document_id": document_id,
            "content": content,
        })
        return result["content"][0]["text"]

    logger.debug("REGISTRY: 3 tools registered (send_email, draft_email, append_to_doc).")
