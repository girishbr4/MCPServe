"""
Configuration Manager
Loads and validates all server configuration from environment variables,
.env file, or config.json at startup.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load .env from project root (two levels up from this file: src/config/ -> root)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent.parent
_env_file = _ROOT / ".env"
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file)
    logger.debug("Loaded .env from %s", _env_file)
else:
    load_dotenv()  # fallback: search up the directory tree


@dataclass(frozen=True)
class ServerConfig:
    """Immutable configuration object for the MCP server."""

    # ── Required ─────────────────────────────────────────────────────────────
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str

    # ── Optional ─────────────────────────────────────────────────────────────
    mcp_transport: str = "stdio"   # "stdio" | "sse"
    port: int = 3000               # Only used when mcp_transport == "sse"
    log_level: str = "INFO"        # DEBUG | INFO | WARNING | ERROR


def _require(key: str) -> str:
    """Read a required environment variable; raise if missing or empty."""
    value = os.getenv(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required configuration key '{key}' is missing or empty. "
            f"Set it in your .env file or as an environment variable."
        )
    return value


def _optional(key: str, default: str) -> str:
    return os.getenv(key, default).strip() or default


def load_config() -> ServerConfig:
    """
    Load configuration with the following priority:
      1. Environment variables (including those loaded from .env)
      2. config.json in the project root (fallback for optional keys only)

    Required keys must always be present in the environment.
    """
    # ── Optional: overlay from config.json if it exists ──────────────────────
    config_json_path = _ROOT / "config.json"
    if config_json_path.exists():
        try:
            with open(config_json_path, "r", encoding="utf-8") as f:
                json_cfg: dict = json.load(f)
            # Only set env vars from JSON if they are not already set
            for k, v in json_cfg.items():
                if not os.getenv(k):
                    os.environ[k] = str(v)
            logger.debug("Overlaid config from %s", config_json_path)
        except json.JSONDecodeError as exc:
            raise ValueError(f"config.json is not valid JSON: {exc}") from exc

    # ── Build config ──────────────────────────────────────────────────────────
    cfg = ServerConfig(
        google_client_id=_require("GOOGLE_CLIENT_ID"),
        google_client_secret=_require("GOOGLE_CLIENT_SECRET"),
        google_refresh_token=_require("GOOGLE_REFRESH_TOKEN"),
        mcp_transport=_optional("MCP_TRANSPORT", "stdio").lower(),
        port=int(_optional("PORT", "3000")),
        log_level=_optional("LOG_LEVEL", "INFO").upper(),
    )

    if cfg.mcp_transport not in ("stdio", "sse"):
        raise ValueError(
            f"Invalid MCP_TRANSPORT '{cfg.mcp_transport}'. Must be 'stdio' or 'sse'."
        )

    return cfg
