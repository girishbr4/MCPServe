"""
Gmail API Adapter
Abstracts all Gmail API client calls behind a clean interface.

Responsibilities:
  - Build RFC 2822 MIME messages and encode them to Base64url
  - Call users.messages.send  (for send_email)
  - Call users.drafts.create  (for draft_email)
  - Handle cc / bcc header injection
"""

import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class GmailAdapter:
    """Thin wrapper around the Gmail API v1 client."""

    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def send_message(
        self,
        to: Union[str, list[str]],
        subject: str,
        body: str,
        cc: Optional[Union[str, list[str]]] = None,
        bcc: Optional[Union[str, list[str]]] = None,
    ) -> dict:
        """
        Compose and immediately send an email.

        Returns:
            The Gmail API response dict containing 'id' and 'threadId'.

        Raises:
            HttpError: On any Google API error (caller maps to structured error).
        """
        raw = self._build_raw_message(to, subject, body, cc, bcc)
        result = (
            self._service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        logger.info("GMAIL: Message sent. id=%s", result.get("id"))
        return result

    def create_draft(
        self,
        to: Union[str, list[str]],
        subject: str,
        body: str,
    ) -> dict:
        """
        Save a composed email as a Gmail draft.

        Returns:
            The Gmail API response dict containing 'id' (draft ID).

        Raises:
            HttpError: On any Google API error.
        """
        raw = self._build_raw_message(to, subject, body)
        result = (
            self._service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        logger.info("GMAIL: Draft created. id=%s", result.get("id"))
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_raw_message(
        to: Union[str, list[str]],
        subject: str,
        body: str,
        cc: Optional[Union[str, list[str]]] = None,
        bcc: Optional[Union[str, list[str]]] = None,
    ) -> str:
        """
        Build an RFC 2822 MIME message and return it Base64url-encoded,
        ready for the Gmail API 'raw' field.
        """
        # Determine if body is HTML or plain text
        content_type = "html" if body.strip().startswith("<") else "plain"

        if content_type == "html":
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg = MIMEText(body, "plain", "utf-8")

        msg["Subject"] = subject
        msg["To"] = _join_addresses(to)

        if cc:
            msg["Cc"] = _join_addresses(cc)
        if bcc:
            msg["Bcc"] = _join_addresses(bcc)

        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _join_addresses(addresses: Union[str, list[str]]) -> str:
    if isinstance(addresses, list):
        return ", ".join(addresses)
    return addresses
