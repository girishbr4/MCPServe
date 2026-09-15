# Google Workspace MCP Server

An agent-agnostic [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that exposes Gmail and Google Docs as tools for any MCP-compliant AI agent (Claude, Gemini, GPT, or custom agents).

## Tools Exposed

| Tool | Description |
|---|---|
| `send_email` | Compose and immediately send an email |
| `draft_email` | Save an email as a Gmail draft for human review |
| `append_to_doc` | Append text to an existing Google Document |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your Google OAuth 2.0 credentials:

```bash
cp .env.example .env
```

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-long-lived-refresh-token
```

> **How to get credentials:** Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create OAuth 2.0 Client ID. Enable the Gmail API and Google Docs API. Then run the interactive login flow once to generate a refresh token (see §Auth below).

### 3. Run the server

**stdio mode** (default — for local agent integrations):
```bash
python -m src.server
```

**SSE mode** (for remote/HTTP agents):
```bash
MCP_TRANSPORT=sse python -m src.server
# Server starts on http://localhost:3000
```

---

## Authentication

The server loads Google OAuth 2.0 credentials in this priority order:

1. **Environment variables** — `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` + `GOOGLE_REFRESH_TOKEN` (recommended for production)
2. **`token.json`** — Cached token from a prior interactive login (auto-generated)
3. **`credentials.json`** — Standard Google OAuth client secrets file → triggers interactive browser consent flow on first run

### Getting a Refresh Token

If you don't have a refresh token yet, place your `credentials.json` in the project root and run:

```bash
python -m src.server
```

The server will open a browser for the Google consent screen, then cache the token in `token.json` for future runs.

---

## Project Structure

```
mcp-google-workspace/
├── src/
│   ├── server.py              # Entry point
│   ├── config/config.py       # Configuration manager
│   ├── auth/auth_manager.py   # OAuth 2.0 credential management
│   ├── tools/
│   │   ├── registry.py        # Tool registry
│   │   ├── gmail/
│   │   │   ├── send_email.py
│   │   │   └── draft_email.py
│   │   └── docs/
│   │       └── append_to_doc.py
│   ├── adapters/
│   │   ├── gmail_adapter.py
│   │   └── docs_adapter.py
│   └── errors/error_handler.py
├── .env.example
├── .gitignore
├── requirements.txt
└── pyproject.toml
```

## Connecting to Claude Desktop

Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/MCPserver"
    }
  }
}
```

## OAuth 2.0 Scopes Required

- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/documents`

## Security

- Credentials are **never** logged or hardcoded
- `.env`, `credentials.json`, and `token.json` are gitignored
- Minimum required OAuth scopes only
