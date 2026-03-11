# Python Rewrite Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the entra-pim-mcp-server from TypeScript/Node.js to Python, distributable via `uvx`/PyPI with identical MCP tool behavior.

**Architecture:** Single-file Python MCP server using FastMCP with Pydantic models for structured I/O. Authentication via `azure-identity` InteractiveBrowserCredential with persistent token cache. Microsoft Graph SDK for all PIM API calls.

**Tech Stack:** Python 3.11+, FastMCP (`mcp[cli]`), `msgraph-sdk`, `azure-identity`, `platformdirs`, `hatchling` build system, `uv` for project management.

**Spec:** `docs/superpowers/specs/2026-03-11-python-rewrite-design.md`

---

## Chunk 1: Project Scaffolding & Cleanup

### Task 1: Remove TypeScript/Node.js artifacts

**Files:**
- Delete: `src/index.ts`
- Delete: `src/auth.ts`
- Delete: `src/tools/list-eligible.ts`
- Delete: `src/tools/activate.ts`
- Delete: `src/tools/` (directory)
- Delete: `package.json`
- Delete: `package-lock.json`
- Delete: `tsconfig.json`
- Delete: `eslint.config.js`
- Delete: `node_modules/` (directory)
- Delete: `docs/` (directory — contains only planning artifacts, not user-facing docs)

- [ ] **Step 1: Delete all TypeScript/Node.js files and directories**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
rm -rf src/ node_modules/ docs/
rm -f package.json package-lock.json tsconfig.json eslint.config.js
```

- [ ] **Step 2: Commit the cleanup**

```bash
git add -A
git commit -s -m "chore: remove TypeScript/Node.js project files

Preparing for Python rewrite. All TypeScript source, Node.js config,
and build artifacts are removed. LICENSE and README.md are kept."
```

### Task 2: Initialize Python project with uv

**Files:**
- Create: `pyproject.toml`
- Create: `src/entra_pim_mcp_server/__init__.py`
- Create: `src/entra_pim_mcp_server/server.py` (stub)
- Modify: `.gitignore` (replace Node.js patterns with Python patterns)

- [ ] **Step 1: Create `.gitignore` for Python**

Replace the existing `.gitignore` with Python-appropriate patterns:

```gitignore
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
.env
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "entra-pim-mcp-server"
version = "0.1.0"
description = "MCP server for Azure Entra PIM — list eligible assignments and activate group/role assignments"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]",
    "msgraph-sdk",
    "azure-identity",
    "platformdirs",
]

[project.scripts]
entra-pim-mcp-server = "entra_pim_mcp_server.server:main"
```

- [ ] **Step 3: Create package `__init__.py`**

```python
# src/entra_pim_mcp_server/__init__.py
```

Empty file — just marks the directory as a Python package.

- [ ] **Step 4: Create stub `server.py`**

```python
# src/entra_pim_mcp_server/server.py
"""Entra PIM MCP Server — list and activate Azure PIM assignments."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("entra-pim-mcp-server")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create directory structure and files**

```bash
mkdir -p src/entra_pim_mcp_server
# Then create .gitignore, pyproject.toml, __init__.py, and server.py as above
```

- [ ] **Step 6: Sync dependencies with uv**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
uv sync
```

Expected: Creates `uv.lock` and installs dependencies into `.venv/`.

- [ ] **Step 7: Verify the stub server starts**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}' | uv run entra-pim-mcp-server 2>/dev/null | head -1
```

Expected: A JSON-RPC response containing `"result"` with server info (not an error).

- [ ] **Step 8: Commit the Python project scaffold**

```bash
git add -A
git commit -s -m "feat: initialize Python project with uv and FastMCP stub

- pyproject.toml with hatchling build system and dependencies
- FastMCP server stub with stdio transport
- Python .gitignore
- uv.lock for reproducible builds"
```

---

## Chunk 2: Authentication Module

### Task 3: Implement authentication and Graph client initialization

**Files:**
- Modify: `src/entra_pim_mcp_server/server.py`

This adds the authentication flow to `server.py`: environment variable validation, cached auth record loading/saving, InteractiveBrowserCredential setup, and singleton Graph client.

- [ ] **Step 1: Add authentication code to `server.py`**

Add the following to `server.py`, between the imports and the `mcp = FastMCP(...)` line:

```python
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from azure.identity import AuthenticationRecord, InteractiveBrowserCredential, TokenCachePersistenceOptions
from msgraph import GraphServiceClient
from mcp.server.fastmcp import FastMCP
from platformdirs import user_config_dir
from pydantic import BaseModel, Field

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

CONFIG_DIR = Path(user_config_dir("entra-pim-mcp-server"))
AUTH_RECORD_PATH = CONFIG_DIR / "auth-record.json"


def _load_auth_record() -> AuthenticationRecord | None:
    try:
        data = AUTH_RECORD_PATH.read_text()
        return AuthenticationRecord.deserialize(data)
    except (FileNotFoundError, ValueError):
        return None


def _save_auth_record(record: AuthenticationRecord) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_RECORD_PATH.write_text(record.serialize())


_client: GraphServiceClient | None = None


async def get_client() -> GraphServiceClient:
    global _client
    if _client is not None:
        return _client

    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    if not tenant_id or not client_id:
        raise RuntimeError("AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required.")

    auth_record = _load_auth_record()

    credential = InteractiveBrowserCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        redirect_uri="http://localhost",
        authentication_record=auth_record,
        cache_persistence_options=TokenCachePersistenceOptions(
            name="entra-pim-mcp-server",
            allow_unencrypted_storage=True,
        ),
    )

    new_record = await asyncio.to_thread(credential.authenticate, scopes=GRAPH_SCOPES)
    if new_record:
        _save_auth_record(new_record)

    _client = GraphServiceClient(credentials=credential, scopes=GRAPH_SCOPES)
    return _client
```

**Key details:**
- `AuthenticationRecord.deserialize()` / `.serialize()` are the Python SDK's equivalents for JSON persistence.
- `credential.authenticate()` is synchronous in the Python SDK, so we wrap with `asyncio.to_thread()`.
- `TokenCachePersistenceOptions(allow_unencrypted_storage=True)` matches the TypeScript `unsafeAllowUnencryptedStorage: true` for WSL support.
- The singleton uses a module-level `_client` variable (no Promise needed in Python async).

Also move the env var validation to `main()`:

```python
def main() -> None:
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    if not tenant_id or not client_id:
        print("Error: AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required.", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")
```

- [ ] **Step 2: Verify the server still starts with required env vars**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
AZURE_TENANT_ID=test AZURE_CLIENT_ID=test \
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}' | uv run entra-pim-mcp-server 2>/dev/null | head -1
```

Expected: JSON-RPC response with server info.

- [ ] **Step 3: Verify the server rejects missing env vars**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
uv run entra-pim-mcp-server 2>&1; echo "exit: $?"
```

Expected: Error message about missing env vars, exit code 1.

- [ ] **Step 4: Commit authentication module**

```bash
git add -A
git commit -s -m "feat(auth): add Azure authentication with token cache persistence

- InteractiveBrowserCredential with browser-based login
- Persistent auth record saved to platform config directory
- Token cache persistence for silent re-authentication
- Environment variable validation (AZURE_TENANT_ID, AZURE_CLIENT_ID)
- Singleton GraphServiceClient pattern"
```

---

## Chunk 3: MCP Tools — list_eligible and activate

### Task 4: Implement the `list_eligible` tool

**Files:**
- Modify: `src/entra_pim_mcp_server/server.py`

- [ ] **Step 1: Add Pydantic models for list_eligible output**

Add after the authentication code, before `main()`:

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
```

- [ ] **Step 2: Add the list_eligible tool**

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_eligible() -> ListEligibleResult:
    """List all eligible Privileged Identity Management (PIM) assignments (Group and Entra Role) for the authenticated user.

    If not authenticated, a browser window will open automatically for login.
    """
    from kiota_abstractions.base_request_configuration import RequestConfiguration

    client = await get_client()

    # Build request configs for queries that need $expand
    group_elig_config = RequestConfiguration(
        query_parameters={"expand": ["group"]},
    )
    role_elig_config = RequestConfiguration(
        query_parameters={"expand": ["roleDefinition"]},
    )

    group_data, group_active, role_data, role_active = await asyncio.gather(
        client.identity_governance.privileged_access.group.eligibility_schedules.filter_by_current_user_with_on(
            "principal"
        ).get(request_configuration=group_elig_config),
        client.identity_governance.privileged_access.group.assignment_schedule_instances.filter_by_current_user_with_on(
            "principal"
        ).get(),
        client.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on("principal").get(
            request_configuration=role_elig_config
        ),
        client.role_management.directory.role_assignment_schedule_instances.filter_by_current_user_with_on(
            "principal"
        ).get(),
    )

    active_group_keys: set[str] = set()
    for a in group_active.value or []:
        active_group_keys.add(f"{a.group_id}:{a.access_id}")

    active_role_ids: set[str] = set()
    for a in role_active.value or []:
        if a.role_definition_id:
            active_role_ids.add(a.role_definition_id)

    assignments: list[Assignment] = []

    for item in group_data.value or []:
        group = getattr(item, "group", None)
        display_name = getattr(group, "display_name", None) if group else None
        end_dt = None
        if item.schedule_info and item.schedule_info.expiration:
            end_dt = item.schedule_info.expiration.end_date_time
        assignments.append(
            Assignment(
                type="Group",
                name=display_name or item.group_id or "",
                id=item.group_id or "",
                role=item.access_id or "",
                member_type=item.member_type or "",
                end_time=end_dt.isoformat() if end_dt else "N/A",
                status="Active" if f"{item.group_id}:{item.access_id}" in active_group_keys else "Eligible",
            )
        )

    for item in role_data.value or []:
        role_def = item.role_definition
        display_name = role_def.display_name if role_def else None
        end_dt = None
        if item.schedule_info and item.schedule_info.expiration:
            end_dt = item.schedule_info.expiration.end_date_time
        assignments.append(
            Assignment(
                type="EntraRole",
                name=display_name or item.role_definition_id or "",
                id=item.role_definition_id or "",
                role=display_name or item.role_definition_id or "",
                member_type="Direct",
                end_time=end_dt.isoformat() if end_dt else "N/A",
                status="Active" if item.role_definition_id in active_role_ids else "Eligible",
            )
        )

    return ListEligibleResult(assignments=assignments)
```

**Key differences from TypeScript:**
- Python Graph SDK uses `snake_case` for all properties (e.g., `group_id` not `groupId`).
- `filter_by_current_user_with_on("principal")` is the Python equivalent of `filterByCurrentUserWithOn('principal')`.
- `getattr(item, "group", None)` safely accesses the `group` navigation property which may not be typed in the SDK.
- Error handling is done by FastMCP — uncaught exceptions are returned as MCP errors automatically.

- [ ] **Step 3: Verify the tool registers (schema check)**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
AZURE_TENANT_ID=test AZURE_CLIENT_ID=test \
  printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | uv run entra-pim-mcp-server 2>/dev/null
```

Expected: Response includes `list_eligible` tool with its schema.

- [ ] **Step 4: Commit list_eligible tool**

```bash
git add -A
git commit -s -m "feat(tools): add list_eligible MCP tool

Lists all eligible PIM assignments (Group and Entra Role) for the
authenticated user. Executes 4 parallel Graph API calls and returns
structured output with Pydantic models."
```

### Task 5: Implement the `activate` tool

**Files:**
- Modify: `src/entra_pim_mcp_server/server.py`

- [ ] **Step 1: Add Pydantic model for activate output**

```python
class ActivateResult(BaseModel):
    status: str
    warnings: list[str] | None = None
```

- [ ] **Step 2: Add the `_get_max_duration` helper function**

Add before the tool definitions:

```python
async def _get_max_duration(client: GraphServiceClient, filter_str: str) -> tuple[timedelta, str | None]:
    """Get the policy-defined maximum activation duration.

    Returns (duration_timedelta, optional_warning).
    Falls back to 8 hours on any failure.
    """
    from kiota_abstractions.base_request_configuration import RequestConfiguration

    default = timedelta(hours=8)
    try:
        policy_config = RequestConfiguration(
            query_parameters={"filter": filter_str},
        )
        policies = await client.policies.role_management_policy_assignments.get(
            request_configuration=policy_config,
        )
        if not policies or not policies.value:
            return default, "No matching policy found; using default duration of 8 hours."

        policy_id = policies.value[0].policy_id
        rules = await client.policies.role_management_policies.by_unified_role_management_policy_id(
            policy_id
        ).rules.get()

        for rule in rules.value or []:
            if rule.id == "Expiration_EndUser_Assignment":
                max_dur = getattr(rule, "maximum_duration", None)
                if max_dur and isinstance(max_dur, timedelta):
                    return max_dur, None
    except Exception as exc:
        return default, f"Failed to retrieve policy maximum duration ({exc}); using default of 8 hours."

    return default, None
```

- [ ] **Step 3: Add the activate tool**

```python
@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def activate(
    justification: str = Field(description="Reason for activating the assignment"),
    group_name: str | None = Field(default=None, description="Name of the group to activate (mutually exclusive with group_id, role_name, role_id)"),
    group_id: str | None = Field(default=None, description="ID of the group to activate (mutually exclusive with group_name, role_name, role_id)"),
    role_name: str | None = Field(default=None, description="Display name of the Entra role to activate (mutually exclusive with group_name, group_id, role_id)"),
    role_id: str | None = Field(default=None, description="ID of the Entra role to activate (mutually exclusive with group_name, group_id, role_name)"),
    duration: int | None = Field(default=None, description="Duration in hours (defaults to policy maximum)"),
) -> ActivateResult:
    """Activate a PIM assignment for a group or Entra role.

    Specify exactly one of: group_name, group_id, role_name, or role_id.
    If not authenticated, a browser window will open automatically for login.
    """
    from kiota_abstractions.base_request_configuration import RequestConfiguration
    from msgraph.generated.models.privileged_access_group_assignment_schedule_request import (
        PrivilegedAccessGroupAssignmentScheduleRequest,
    )
    from msgraph.generated.models.privileged_access_group_relationships import PrivilegedAccessGroupRelationships
    from msgraph.generated.models.request_schedule import RequestSchedule
    from msgraph.generated.models.expiration_pattern import ExpirationPattern
    from msgraph.generated.models.expiration_pattern_type import ExpirationPatternType
    from msgraph.generated.models.schedule_request_actions import ScheduleRequestActions
    from msgraph.generated.models.unified_role_assignment_schedule_request import (
        UnifiedRoleAssignmentScheduleRequest,
    )

    identifiers = [v for v in (group_name, group_id, role_name, role_id) if v is not None]
    if len(identifiers) != 1:
        raise ValueError("Specify exactly one of: group_name, group_id, role_name, or role_id.")

    client = await get_client()

    me_config = RequestConfiguration(query_parameters={"select": ["id"]})
    me = await client.me.get(request_configuration=me_config)
    if not me or not me.id:
        raise RuntimeError("Failed to retrieve current user ID")
    principal_id = me.id

    warnings: list[str] = []

    if group_name or group_id:
        group_elig_config = RequestConfiguration(query_parameters={"expand": ["group"]})
        eligible = await (
            client.identity_governance.privileged_access.group.eligibility_schedules.filter_by_current_user_with_on(
                "principal"
            ).get(request_configuration=group_elig_config)
        )

        match = None
        if group_id:
            match = next((i for i in (eligible.value or []) if i.group_id == group_id), None)
            if not match:
                raise ValueError(f'No eligible group assignment found with ID "{group_id}"')
        else:
            for item in eligible.value or []:
                group_obj = getattr(item, "group", None)
                dn = getattr(group_obj, "display_name", None) if group_obj else None
                if dn and dn.lower() == group_name.lower():
                    match = item
                    break
            if not match:
                raise ValueError(f'No eligible group assignment found with name "{group_name}"')
            if not match.group_id:
                raise ValueError(f'Eligible group assignment for "{group_name}" has no group ID')

        resolved_group_id = match.group_id
        # access_id may be an enum; use .value to get the raw string for OData filters
        access_id_raw = match.access_id
        access_id_str = access_id_raw.value if hasattr(access_id_raw, "value") else str(access_id_raw or "member")

        if duration is not None:
            duration_td = timedelta(hours=duration)
        else:
            duration_td, warn = await _get_max_duration(
                client,
                f"scopeId eq '{resolved_group_id}' and scopeType eq 'Group' and roleDefinitionId eq '{access_id_str}'",
            )
            if warn:
                warnings.append(warn)

        access_id_enum = (
            PrivilegedAccessGroupRelationships.Owner
            if access_id_str == "owner"
            else PrivilegedAccessGroupRelationships.Member
        )

        request_body = PrivilegedAccessGroupAssignmentScheduleRequest(
            action=ScheduleRequestActions.SelfActivate,
            principal_id=principal_id,
            group_id=resolved_group_id,
            access_id=access_id_enum,
            justification=justification,
            schedule_info=RequestSchedule(
                start_date_time=datetime.now(timezone.utc),
                expiration=ExpirationPattern(
                    type=ExpirationPatternType.AfterDuration,
                    duration=duration_td,
                ),
            ),
        )

        result = await client.identity_governance.privileged_access.group.assignment_schedule_requests.post(
            request_body
        )
        status = result.status if result else "Pending"

    else:
        # Role activation
        if role_id:
            resolved_role_id = role_id
            eligible = await (
                client.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on(
                    "principal"
                ).get()
            )
            match = next((i for i in (eligible.value or []) if i.role_definition_id == role_id), None)
            scope_id = match.directory_scope_id if match and match.directory_scope_id else "/"
        else:
            role_elig_config = RequestConfiguration(query_parameters={"expand": ["roleDefinition"]})
            eligible = await (
                client.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on(
                    "principal"
                ).get(request_configuration=role_elig_config)
            )
            match = next(
                (
                    i
                    for i in (eligible.value or [])
                    if i.role_definition and (i.role_definition.display_name or "").lower() == role_name.lower()
                ),
                None,
            )
            if not match:
                raise ValueError(f'No eligible role assignment found with name "{role_name}"')
            if not match.role_definition_id:
                raise ValueError(f'Eligible role assignment for "{role_name}" has no role definition ID')
            resolved_role_id = match.role_definition_id
            scope_id = match.directory_scope_id or "/"

        if duration is not None:
            duration_td = timedelta(hours=duration)
        else:
            duration_td, warn = await _get_max_duration(
                client,
                f"scopeId eq '{scope_id}' and scopeType eq 'DirectoryRole' and roleDefinitionId eq '{resolved_role_id}'",
            )
            if warn:
                warnings.append(warn)

        request_body = UnifiedRoleAssignmentScheduleRequest(
            action=ScheduleRequestActions.SelfActivate,
            principal_id=principal_id,
            role_definition_id=resolved_role_id,
            directory_scope_id=scope_id,
            justification=justification,
            schedule_info=RequestSchedule(
                start_date_time=datetime.now(timezone.utc),
                expiration=ExpirationPattern(
                    type=ExpirationPatternType.AfterDuration,
                    duration=duration_td,
                ),
            ),
        )

        result = await client.role_management.directory.role_assignment_schedule_requests.post(request_body)
        status = result.status if result else "Pending"

    return ActivateResult(status=status, warnings=warnings if warnings else None)
```

**Key details:**
- Uses Microsoft Graph SDK Python model classes for the POST request body.
- `ScheduleRequestActions.SelfActivate` is the Python enum for the `"selfActivate"` action.
- `PrivilegedAccessGroupRelationships.Member`/`.Owner` maps the access ID string to the SDK enum.
- `ExpirationPatternType.AfterDuration` with a `timedelta` object (not ISO 8601 string — the Python SDK serializes timedelta internally).
- The `access_id` from eligible assignments may be an enum; use `.value` to get the raw string for OData filter construction.
- `RequestConfiguration(query_parameters=...)` is required for all `.get()` calls that need query params — the Python SDK does not accept `query_parameters` as a keyword to `.get()` directly.
- `_get_max_duration` returns `timedelta` directly; `maximum_duration` from the policy rule is already a `timedelta` in the Python SDK.

- [ ] **Step 4: Verify both tools register**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
AZURE_TENANT_ID=test AZURE_CLIENT_ID=test \
  printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | uv run entra-pim-mcp-server 2>/dev/null
```

Expected: Response includes both `list_eligible` and `activate` tools with their schemas.

- [ ] **Step 5: Commit activate tool**

```bash
git add -A
git commit -s -m "feat(tools): add activate MCP tool

Activates a PIM assignment for a group or Entra role. Supports
lookup by name (case-insensitive) or ID. Fetches policy-defined
maximum duration with PT8H fallback. Uses Pydantic models for
structured output."
```

---

## Chunk 4: README & Final Polish

### Task 6: Rewrite README for Python

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README.md**

Replace the entire README with Python-focused content. Keep the same sections but update:
- Prerequisites: Python 3.11+ and `uv` instead of Node.js
- Usage: `uvx entra-pim-mcp-server` instead of `npx`
- MCP client config: `uvx` command instead of `npx`
- App registration section: keep as-is (Azure setup is the same)
- Available tools section: keep as-is (tool names/behavior unchanged)
- Architecture diagram: same, just note it's Python now

The full README content:

```markdown
# entra-pim-mcp-server

An MCP (Model Context Protocol) server for Azure Entra PIM (Privileged Identity Management). List eligible assignments and activate group or Entra role assignments — all through your MCP-compatible AI client.

## Features

- **List eligible PIM assignments** — view all Group and Entra Role assignments you're eligible for, with their activation status
- **Activate PIM assignments** — activate group or role assignments by name or ID, with a justification and optional duration
- **Automatic browser authentication** — opens your browser automatically when login is needed, with persistent token caching
- **No secrets required** — uses a public client app registration, no client secret necessary

## Prerequisites

- Python 3.11 or later (or [uv](https://docs.astral.sh/uv/) which manages Python automatically)
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

### Run with uvx (recommended)

```bash
AZURE_TENANT_ID="your-tenant-id" AZURE_CLIENT_ID="your-client-id" uvx entra-pim-mcp-server
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
      "args": ["entra-pim-mcp-server"],
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
      "args": ["entra-pim-mcp-server"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id",
        "AZURE_CLIENT_ID": "your-client-id"
      }
    }
  }
}
```

### Cursor

Add to your Cursor MCP configuration:

```json
{
  "mcpServers": {
    "entra-pim": {
      "command": "uvx",
      "args": ["entra-pim-mcp-server"],
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
- **member_type** — Membership type (e.g., `Direct`)
- **status** — `Active` (currently activated) or `Eligible` (available to activate)
- **end_time** — When the eligibility expires

### `activate`

Activates a PIM assignment for a group or Entra role.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `group_name` | string | One of these four | Name of the group to activate |
| `group_id` | string | | ID of the group to activate |
| `role_name` | string | | Display name of the Entra role |
| `role_id` | string | | ID of the Entra role |
| `justification` | string | Yes | Reason for activation |
| `duration` | number | No | Duration in hours (defaults to policy maximum) |

Specify exactly **one** identifier (`group_name`, `group_id`, `role_name`, or `role_id`).

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
```

- [ ] **Step 2: Commit README**

```bash
git add README.md
git commit -s -m "docs: rewrite README for Python/uvx

Update all instructions from Node.js/npx to Python/uvx. Add Cursor
config example. Keep app registration and tool documentation unchanged."
```

### Task 7: Final verification

- [ ] **Step 1: Verify `uv run` and `uvx` entry point works**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
AZURE_TENANT_ID=test AZURE_CLIENT_ID=test uv run entra-pim-mcp-server --help 2>&1 || true
```

- [ ] **Step 2: Verify tool listing end-to-end**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
AZURE_TENANT_ID=test AZURE_CLIENT_ID=test \
  printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | uv run entra-pim-mcp-server 2>/dev/null | python3 -m json.tool
```

Expected: Pretty-printed JSON showing both `list_eligible` and `activate` tools with correct schemas.

- [ ] **Step 3: Verify env var rejection**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
uv run entra-pim-mcp-server 2>&1
echo "Exit code: $?"
```

Expected: Error message about missing env vars, exit code 1.

- [ ] **Step 4: Verify clean git status**

```bash
cd /home/mnaser/src/github.com/vexxhost/entra-pim-mcp-server
git --no-pager status
git --no-pager log --oneline -10
```

Expected: Clean working tree, commits for each task.
