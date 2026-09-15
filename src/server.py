"""
Google Workspace MCP Server — Entry Point (MCP SDK v2)

Initialises the MCP server with the correct transport (stdio or HTTP SSE),
loads configuration and auth, registers all tools, then starts serving.

Usage:
    python -m src.server          # stdio transport (default)
    MCP_TRANSPORT=sse python -m src.server   # HTTP SSE transport
"""

import asyncio
import logging
import sys

from mcp.server.mcpserver import MCPServer

from src.config.config import load_config
from src.auth.auth_manager import AuthManager
from src.tools.registry import register_all_tools

# ---------------------------------------------------------------------------
# Logging — configured before anything else so all modules can use it
# ---------------------------------------------------------------------------

def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # MCP stdio uses stdout; keep logs on stderr
    )


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_server() -> tuple[MCPServer, object]:
    """Build and configure the MCP server. Returns (server, cfg)."""
    cfg = load_config()
    _setup_logging(cfg.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting Google Workspace MCP Server (transport=%s).", cfg.mcp_transport)

    auth_manager = AuthManager(cfg)

    # Eagerly validate credentials at startup so failures surface immediately
    try:
        auth_manager.get_credentials()
        logger.info("Google credentials validated successfully.")
    except RuntimeError as exc:
        logger.critical("Credential validation failed: %s", exc)
        sys.exit(1)

    server = MCPServer("google-workspace-mcp")
    register_all_tools(server, auth_manager)
    logger.info("All tools registered: send_email, draft_email, append_to_doc.")

    return server, cfg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    server, cfg = create_server()
    logger = logging.getLogger(__name__)

    if cfg.mcp_transport == "sse":
        import uvicorn
        app = server.sse_app()
        logger.info("SSE transport listening on port %d.", cfg.port)
        uvicorn.run(app, host="0.0.0.0", port=cfg.port, log_level=cfg.log_level.lower())
    else:
        # Default: stdio
        logger.info("Running in stdio mode.")
        asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
