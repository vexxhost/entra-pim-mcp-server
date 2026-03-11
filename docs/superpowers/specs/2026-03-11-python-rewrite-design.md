# Entra PIM MCP Server — Python Rewrite Design

## Problem

The project is a TypeScript/Node.js MCP server for Azure Entra Privileged Identity Management. The owner wants to rewrite it in Python so it can be distributed via `uvx` (and eventually PyPI), eliminating Node.js toolchain requirements and simplifying distribution.

## Approach

Rewrite the entire project in Python using FastMCP (official MCP SDK), `msgraph-sdk` (official Microsoft Graph Python SDK), and `azure-identity` for authentication. The Python version preserves identical tool names, schemas, and behavior. All TypeScript/Node.js artifacts are removed.

## Project Structure

```
entra-pim-mcp-server/
├── pyproject.toml                    # Packaging, dependencies, entry point
├── src/
│   └── entra_pim_mcp_server/
│       ├── __init__.py               # Package version
│       └── server.py                 # All logic: auth, tools, main()
├── README.md                         # Rewritten for Python
├── LICENSE                           # Apache-2.0 (unchanged)
└── .gitignore                        # Python-specific
```

Single-file architecture: all logic lives in `server.py` (~300 lines). The project is small enough that splitting into multiple modules adds overhead without benefit.

## Packaging & Distribution

**pyproject.toml** defines:
- `[project.scripts]` entry point: `entra-pim-mcp-server = "entra_pim_mcp_server.server:main"`
- Build system: hatchling
- Python requirement: `>=3.11`
- Published to PyPI as `entra-pim-mcp-server`

**Usage:** `uvx entra-pim-mcp-server` installs and runs in one command.

**MCP client configuration:**
```json
{
  "command": "uvx",
  "args": ["entra-pim-mcp-server"],
  "env": {
    "AZURE_TENANT_ID": "<tenant-id>",
    "AZURE_CLIENT_ID": "<client-id>"
  }
}
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp[cli]` | FastMCP server framework |
| `msgraph-sdk` | Microsoft Graph API client |
| `azure-identity` | Azure authentication (InteractiveBrowserCredential) |
| `platformdirs` | Cross-platform config directory paths |

## Authentication

### Flow

1. On first tool call, `get_client()` is called (singleton pattern).
2. Load cached `AuthenticationRecord` from `~/.config/entra-pim-mcp-server/auth-record.json` (Linux) or OS-appropriate path via `platformdirs`.
3. Create `InteractiveBrowserCredential` with:
   - `tenant_id` from `AZURE_TENANT_ID` env var
   - `client_id` from `AZURE_CLIENT_ID` env var
   - `redirect_uri="http://localhost"`
   - `authentication_record` from cache (if available)
   - `cache_persistence_options` with `name="entra-pim-mcp-server"` and `allow_unencrypted_storage=True`
4. Call `credential.authenticate(scopes=GRAPH_SCOPES)` — opens browser if no valid cached token.
5. Save new `AuthenticationRecord` to disk.
6. Create `GraphServiceClient(credential, scopes=GRAPH_SCOPES)`.
7. Cache client for subsequent calls.

### Graph API Scopes

```python
GRAPH_SCOPES = [
    "User.Read",
    "Group.Read.All",
    "PrivilegedAssignmentSchedule.ReadWrite.AzureADGroup",
    "PrivilegedEligibilitySchedule.Read.AzureADGroup",
    "RoleManagementPolicy.Read.AzureADGroup",
    "RoleEligibilitySchedule.Read.Directory",
    "RoleAssignmentSchedule.ReadWrite.Directory",
    "RoleManagementPolicy.Read.Directory",
]
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_TENANT_ID` | Yes | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Yes | App registration client ID |

Server exits with error if either is missing.

## MCP Tools

### Data Models (Pydantic)

```python
class Assignment(BaseModel):
    type: Literal["Group", "EntraRole"]
    name: str
    id: str
    role: str
    member_type: str
    end_time: str
    status: Literal["Active", "Eligible"]

class ListEligibleResult(BaseModel):
    assignments: list[Assignment]

class ActivateResult(BaseModel):
    status: str
    warnings: list[str] | None = None
```

### Tool: `list_eligible`

**Parameters:** None
**Returns:** `ListEligibleResult`
**Annotations:** readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False

**Logic:**
1. Get Graph client (triggers auth if needed).
2. Execute 4 parallel Graph API requests via `asyncio.gather`:
   - Group eligibility schedules (expand=group)
   - Group active assignment schedule instances
   - Role eligibility schedules (expand=roleDefinition)
   - Role active assignment schedule instances
3. Build sets of active group keys (`groupId:accessId`) and active role IDs.
4. Map group eligibilities to `Assignment` objects, marking status as "Active" or "Eligible". `memberType` comes from the eligibility record.
5. Map role eligibilities to `Assignment` objects, marking status as "Active" or "Eligible". `memberType` is hardcoded as `"Direct"`.
6. Return combined list.

### Tool: `activate`

**Parameters:**
- `group_name: str | None` — Mutually exclusive identifier
- `group_id: str | None` — Mutually exclusive identifier
- `role_name: str | None` — Mutually exclusive identifier
- `role_id: str | None` — Mutually exclusive identifier
- `justification: str` — Required reason for activation
- `duration: int | None` — Optional duration in hours (defaults to policy maximum)

**Returns:** `ActivateResult`
**Annotations:** readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False

**Logic:**
1. Validate exactly one identifier is provided.
2. Get Graph client.
3. Fetch current user's principal ID via `GET /me?$select=id`.
4. For groups:
   a. Resolve group ID and access level from eligible assignments (by name with case-insensitive match, or by ID). Default access level to `"member"` if not present.
   b. Get max duration from policy (`Expiration_EndUser_Assignment` rule), or use provided duration. On policy fetch failure, fall back to `PT8H` (8 hours) and add a warning.
   c. POST `selfActivate` request to group assignment schedule requests endpoint with `principalId`, `groupId`, `accessId`, `justification`, and `scheduleInfo`.
5. For roles:
   a. Resolve role ID and directory scope from eligible assignments (by name with case-insensitive match, or by ID). Default directory scope to `"/"` if not present.
   b. Get max duration from policy, or use provided duration. Same fallback behavior as groups.
   c. POST `selfActivate` request to role assignment schedule requests endpoint with `principalId`, `roleDefinitionId`, `directoryScopeId`, `justification`, and `scheduleInfo`.
6. Return status and any warnings.

**Error handling:** Catch exceptions, return error text via MCP error response.

## Graph API Endpoints Used

### User
- `GET /me?$select=id`

### Group PIM
- `GET /identityGovernance/privilegedAccess/group/eligibilitySchedules/filterByCurrentUser(on='principal')?$expand=group`
- `GET /identityGovernance/privilegedAccess/group/assignmentScheduleInstances/filterByCurrentUser(on='principal')`
- `POST /identityGovernance/privilegedAccess/group/assignmentScheduleRequests`

### Role PIM
- `GET /roleManagement/directory/roleEligibilitySchedules/filterByCurrentUser(on='principal')?$expand=roleDefinition`
- `GET /roleManagement/directory/roleAssignmentScheduleInstances/filterByCurrentUser(on='principal')`
- `POST /roleManagement/directory/roleAssignmentScheduleRequests`

### Policies
- `GET /policies/roleManagementPolicyAssignments?$filter=...`
- `GET /policies/roleManagementPolicies/{policyId}/rules`

## Files Removed

All TypeScript/Node.js artifacts:
- `src/` (TypeScript source files)
- `package.json`, `package-lock.json`
- `tsconfig.json`, `eslint.config.js`
- `node_modules/`

## Files Kept

- `LICENSE` — Apache-2.0 (unchanged)
- `README.md` — Rewritten for Python/uvx usage
- `.git/` — History preserved
