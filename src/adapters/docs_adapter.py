"""
Google Docs API Adapter
Abstracts all Google Docs API client calls behind a clean interface.

Responsibilities:
  - Fetch the current end-index of a document body (documents.get)
  - Construct a batchUpdate request with insertText at the end index
  - Call documents.batchUpdate (for append_to_doc)
"""

import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class DocsAdapter:
    """Thin wrapper around the Google Docs API v1 client."""

    def __init__(self, credentials: Credentials) -> None:
        self._service = build("docs", "v1", credentials=credentials, cache_discovery=False)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def append_text(self, document_id: str, content: str) -> dict:
        """
        Append ``content`` to the end of the Google Document identified
        by ``document_id``.

        Strategy (per architecture.md §7.3):
          1. GET /documents/{id}  →  find endIndex of the last body element
          2. POST /documents/{id}:batchUpdate  →  insertText at endIndex - 1

        Returns:
            The batchUpdate API response dict.

        Raises:
            HttpError: On any Google API error (caller maps to structured error).
            ValueError: If the document has an unexpected structure.
        """
        # Step 1 — Fetch document to find end index
        logger.info("DOCS: Fetching document %s to find end index.", document_id)
        doc = (
            self._service.documents()
            .get(documentId=document_id)
            .execute()
        )

        end_index = self._get_body_end_index(doc)
        logger.info("DOCS: Resolved end index = %d for document %s.", end_index, document_id)

        # Step 2 — Insert text at end index
        requests = [
            {
                "insertText": {
                    "location": {"index": end_index},
                    "text": content,
                }
            }
        ]

        result = (
            self._service.documents()
            .batchUpdate(documentId=document_id, body={"requests": requests})
            .execute()
        )
        logger.info("DOCS: Content appended to document %s.", document_id)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_body_end_index(doc: dict) -> int:
        """
        Walk the document body content list and return the insertion index
        for appending.

        The Google Docs API uses 1-based indexes. The very last structural
        element's endIndex is the end of the document. We insert at
        endIndex - 1 to stay within the document boundary (before the
        implicit final newline kept by the Docs API).
        """
        body = doc.get("body", {})
        content = body.get("content", [])

        if not content:
            raise ValueError(
                "Document body has no content array. "
                "Cannot determine insertion index."
            )

        # The last element in content[] has the highest endIndex
        last_element = content[-1]
        end_index = last_element.get("endIndex", 1)

        # Insert just before the trailing newline the Docs API always keeps
        return max(1, end_index - 1)
