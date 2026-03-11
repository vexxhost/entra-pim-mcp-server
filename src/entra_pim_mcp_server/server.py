"""Entra PIM MCP Server — list and activate Azure PIM assignments."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Literal

from azure.identity import (
    AuthenticationRecord,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
)
from mcp.server.fastmcp import FastMCP
from msgraph import GraphServiceClient
from platformdirs import user_config_dir
from pydantic import BaseModel

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
        raise RuntimeError(
            "AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required."
        )

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


mcp = FastMCP("entra-pim-mcp-server")


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


def main() -> None:
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    if not tenant_id or not client_id:
        print(
            "Error: AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required.",
            file=sys.stderr,
        )
        sys.exit(1)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
