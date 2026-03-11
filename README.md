# entra-pim-mcp-server

An MCP (Model Context Protocol) server for Azure Entra PIM (Privileged Identity Management). List eligible assignments and activate group or Entra role assignments — all through your MCP-compatible AI client.

## Features

- **List eligible PIM assignments** — view all Group and Entra Role assignments you're eligible for, with their activation status
- **Activate PIM assignments** — activate group or role assignments by name or ID, with a justification and optional duration
- **Automatic browser authentication** — opens your browser automatically when login is needed, with persistent token caching
- **No secrets required** — uses a public client app registration, no client secret necessary

## Prerequisites

- Python 3.10 or later (or [uv](https://docs.astral.sh/uv/) to run without installing Python manually)
- An Azure Entra ID tenant with PIM enabled
- An Entra ID app registration (public client) with the required permissions

## Entra ID App Registration

1. Go to [Azure Portal → Microsoft Entra ID → App registrations](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps)
2. Click **New registration**
3. Set:
   - **Name**: e.g., `Entra PIM MCP Server`
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: Select **Web** and add `http://localhost`
4. After creation, go to **Authentication**:
   - Enable **Allow public client flows** → Yes
5. Go to **API permissions** and add the following **Microsoft Graph** delegated permissions:

   | Permission | Description |
   |------------|-------------|
   | `User.Read` | Sign in and read user profile |
   | `Group.Read.All` | Read all groups |
   | `PrivilegedAssignmentSchedule.ReadWrite.AzureADGroup` | Read/write privileged access group assignment schedules |
   | `PrivilegedEligibilitySchedule.Read.AzureADGroup` | Read privileged access group eligibility schedules |
   | `RoleManagementPolicy.Read.AzureADGroup` | Read group role management policies |
   | `RoleEligibilitySchedule.Read.Directory` | Read role eligibility schedules |
   | `RoleAssignmentSchedule.ReadWrite.Directory` | Read/write role assignment schedules |
   | `RoleManagementPolicy.Read.Directory` | Read role management policies |

6. Click **Grant admin consent** (requires admin privileges)
7. Note down the **Application (client) ID** and your **Directory (tenant) ID**

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_TENANT_ID` | Yes | Your Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Yes | The app registration client ID |

## Usage

### Run directly with uvx

```bash
AZURE_TENANT_ID="your-tenant-id" AZURE_CLIENT_ID="your-client-id" uvx --from git+https://github.com/vexxhost/entra-pim-mcp-server entra-pim-mcp-server
```

### Run from source

```bash
git clone https://github.com/vexxhost/entra-pim-mcp-server.git
cd entra-pim-mcp-server
uv sync
AZURE_TENANT_ID="..." AZURE_CLIENT_ID="..." uv run entra-pim-mcp-server
```

## MCP Client Configuration

### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "entra-pim": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/vexxhost/entra-pim-mcp-server", "entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id",
        "AZURE_CLIENT_ID": "your-client-id"
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
      "args": ["--from", "git+https://github.com/vexxhost/entra-pim-mcp-server", "entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id",
        "AZURE_CLIENT_ID": "your-client-id"
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
      "args": ["--from", "git+https://github.com/vexxhost/entra-pim-mcp-server", "entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id",
        "AZURE_CLIENT_ID": "your-client-id"
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
| `access_id` | string | No | Access relationship for groups: `member` (default) or `owner` |
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
