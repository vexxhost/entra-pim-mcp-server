# entra-pim-mcp-server

An MCP (Model Context Protocol) server for Azure Entra PIM (Privileged Identity Management). List eligible assignments and activate group or Entra role assignments — all through your MCP-compatible AI client.

## Features

- **List eligible PIM assignments** — view all Group and Entra Role assignments you're eligible for, with their activation status
- **Activate PIM assignments** — activate group or role assignments by name or ID, with a justification and optional duration
- **Automatic browser authentication** — opens your browser automatically when login is needed, with persistent token caching
- **No app registration required** — uses the Microsoft Graph PowerShell well-known client ID, no setup needed
- **No secrets required** — uses delegated authentication, no client secret necessary

## Prerequisites

- Python 3.10 or later (or [uv](https://docs.astral.sh/uv/) to run without installing Python manually)
- An Azure Entra ID tenant with PIM enabled

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_TENANT_ID` | Yes | Your Azure AD tenant ID |

## Usage

### Run directly with uvx

```bash
AZURE_TENANT_ID="your-tenant-id" uvx entra-pim-mcp-server
```

### Run from source

```bash
git clone https://github.com/vexxhost/entra-pim-mcp-server.git
cd entra-pim-mcp-server
uv sync
AZURE_TENANT_ID="..." uv run entra-pim-mcp-server
```

## MCP Client Configuration

### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "entra-pim": {
      "command": "uvx",
      "args": ["entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id"
      }
    }
  }
}
```

### VS Code / GitHub Copilot

Add to your `.vscode/mcp.json`:

```json
{
  "servers": {
    "entra-pim": {
      "command": "uvx",
      "args": ["entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id"
      }
    }
  }
}
```

### Cursor

Add to your Cursor MCP settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "entra-pim": {
      "command": "uvx",
      "args": ["entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id"
      }
    }
  }
}
```

## Authentication

This server uses **interactive browser authentication**. When you first call any PIM tool:

1. Your default browser opens automatically to the Microsoft Entra ID login page
2. You sign in and grant consent
3. The browser shows "Authentication complete" — you can close the tab
4. The token and authentication record are cached locally

On subsequent calls (and server restarts), the cached token is used silently — **no re-authentication needed** until the token expires.

## Available Tools

### `list_eligible`

Lists all eligible PIM assignments (both Group and Entra Role) for the authenticated user.

Returns structured JSON with an `assignments` array, where each assignment has:
- **type** — `Group` or `EntraRole`
- **name** — Group or role display name
- **id** — Group or role definition ID
- **role** — Access level (e.g., `member`, `owner`) or role name
- **memberType** — Membership type (e.g., `Direct`)
- **status** — `Active` (currently activated) or `Eligible` (available to activate)
- **endTime** — When the eligibility expires

### `activate`

Activates a PIM assignment for a group or Entra role.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Name of the group or Entra role to activate (case-insensitive) |
| `justification` | string | Yes | Reason for activation |
| `duration` | number | No | Duration in hours (defaults to policy maximum) |
| `directory_scope_id` | string | No | Directory scope for Entra roles (default: `/`) |

## Architecture

```
┌─────────────┐     stdio      ┌──────────────────┐    Graph API    ┌──────────────┐
│  MCP Client │ ◄────────────► │  MCP Server      │ ──────────────► │ Microsoft    │
│  (Claude,   │                │  (this project)  │                 │ Graph API    │
│   Cursor,   │                │                  │                 │              │
│   VS Code)  │                └──────────────────┘                 └──────────────┘
└─────────────┘                        │
                                       │ Auto Browser Login
                                       ▼
                                ┌──────────────┐
                                │ Microsoft    │
                                │ Entra ID     │
                                └──────────────┘
```

1. MCP client starts the server as a subprocess (stdio transport)
2. When a PIM tool is called and no cached token exists, the browser opens for Entra ID login
3. After authentication, the token and auth record are cached locally
4. All MCP tool calls use this token for Microsoft Graph PIM operations
5. On restart, the cached token is used silently

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
