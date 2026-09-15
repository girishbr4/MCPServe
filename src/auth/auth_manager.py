"""
Auth Manager
Manages Google OAuth 2.0 credentials across the server lifecycle.

Priority order for credential loading:
  1. Environment variables (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN)
  2. credentials.json (Google OAuth client secrets file)
  3. token.json (cached token from a prior interactive login)

Tokens are NEVER logged or exposed in error messages.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config.config import ServerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required OAuth 2.0 scopes — minimum necessary
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/documents",
]

_ROOT = Path(__file__).resolve().parent.parent.parent
_TOKEN_FILE = _ROOT / "token.json"
_CREDENTIALS_FILE = _ROOT / "credentials.json"


class AuthManager:
    """
    Singleton-style auth manager that holds the active Google Credentials
    and provides a method to retrieve a fresh credential object on demand.
    """

    def __init__(self, cfg: ServerConfig) -> None:
        self._cfg = cfg
        self._creds: Optional[Credentials] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_credentials(self) -> Credentials:
        """
        Return valid (possibly refreshed) Google Credentials.
        Raises RuntimeError with a safe message if auth fails entirely.
        """
        if self._creds is None:
            self._creds = self._load_credentials()

        if not self._creds.valid:
            self._creds = self._refresh_or_reauth(self._creds)

        return self._creds

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_credentials(self) -> Credentials:
        """
        Load credentials using the priority chain described in architecture.md.
        """
        # ── Priority 1: Environment variables ──────────────────────────────
        if (
            self._cfg.google_client_id
            and self._cfg.google_client_secret
            and self._cfg.google_refresh_token
        ):
            logger.info("AUTH: Loading credentials from environment variables.")
            creds = Credentials(
                token=None,  # will be populated on first refresh
                refresh_token=self._cfg.google_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self._cfg.google_client_id,
                client_secret=self._cfg.google_client_secret,
                scopes=SCOPES,
            )
            # Force an immediate refresh to obtain a valid access token
            try:
                creds.refresh(Request())
                logger.info("AUTH: Access token obtained via refresh.")
                self._save_token(creds)
            except RefreshError as exc:
                raise RuntimeError(
                    "AUTH_EXPIRED: Could not refresh access token using the provided "
                    "GOOGLE_REFRESH_TOKEN. Please re-authorize."
                ) from exc
            return creds

        # ── Priority 2: token.json (cached interactive login) ───────────────
        if _TOKEN_FILE.exists():
            logger.info("AUTH: Loading credentials from %s.", _TOKEN_FILE)
            creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                return self._refresh_or_reauth(creds)

        # ── Priority 3: credentials.json → interactive OAuth consent flow ───
        if _CREDENTIALS_FILE.exists():
            logger.info(
                "AUTH: No cached token found. Starting interactive OAuth flow "
                "using %s.",
                _CREDENTIALS_FILE,
            )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=True)
            self._save_token(creds)
            logger.info("AUTH: Interactive login complete. Token cached.")
            return creds

        raise RuntimeError(
            "AUTH_FAILED: No Google credentials found. "
            "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN "
            "in your .env file, or place a credentials.json in the project root."
        )

    def _refresh_or_reauth(self, creds: Credentials) -> Credentials:
        """Attempt a silent token refresh. Raises RuntimeError on failure."""
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("AUTH: Access token refreshed successfully.")
                self._save_token(creds)
                return creds
            except (RefreshError, TransportError) as exc:
                raise RuntimeError(
                    "AUTH_EXPIRED: Authentication Expired. "
                    "Please re-authorize the server with Google."
                ) from exc
        raise RuntimeError(
            "AUTH_EXPIRED: No refresh token available. "
            "Please re-authorize the server with Google."
        )

    @staticmethod
    def _save_token(creds: Credentials) -> None:
        """Persist the token to disk so subsequent runs skip the consent flow."""
        try:
            with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.debug("AUTH: Token saved to %s.", _TOKEN_FILE)
        except OSError as exc:
            # Non-fatal — just log; we can still operate without caching
            logger.warning("AUTH: Could not save token.json: %s", exc)
