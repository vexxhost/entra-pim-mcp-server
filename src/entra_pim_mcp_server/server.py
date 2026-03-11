"""Entra PIM MCP Server — list and activate Azure PIM assignments."""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Literal

from azure.identity import (
    AuthenticationRecord,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
)
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from msgraph.graph_service_client import GraphServiceClient
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


class ActivateResult(BaseModel):
    message: str
    name: str
    type: Literal["Group", "EntraRole"]
    duration: str


mcp = FastMCP("entra-pim-mcp-server")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def list_eligible() -> ListEligibleResult:
    """List all eligible Privileged Identity Management (PIM) assignments (Group and Entra Role) for the authenticated user.

    If not authenticated, a browser window will open automatically for login.
    """
    from kiota_abstractions.base_request_configuration import RequestConfiguration
    from msgraph.generated.identity_governance.privileged_access.group.eligibility_schedules.filter_by_current_user_with_on.filter_by_current_user_with_on_request_builder import (
        FilterByCurrentUserWithOnRequestBuilder as GroupEligFilterBuilder,
    )
    from msgraph.generated.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on.filter_by_current_user_with_on_request_builder import (
        FilterByCurrentUserWithOnRequestBuilder as RoleEligFilterBuilder,
    )

    client = await get_client()

    group_elig_config = RequestConfiguration(
        query_parameters=GroupEligFilterBuilder.FilterByCurrentUserWithOnRequestBuilderGetQueryParameters(
            expand=["group"],
        ),
    )
    role_elig_config = RequestConfiguration(
        query_parameters=RoleEligFilterBuilder.FilterByCurrentUserWithOnRequestBuilderGetQueryParameters(
            expand=["roleDefinition"],
        ),
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
    if group_active:
        for a in group_active.value or []:
            active_group_keys.add(f"{a.group_id}:{a.access_id}")

    active_role_ids: set[str] = set()
    if role_active:
        for a in role_active.value or []:
            if a.role_definition_id:
                active_role_ids.add(a.role_definition_id)

    assignments: list[Assignment] = []

    if group_data:
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

    if role_data:
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


async def _get_max_duration(
    client: GraphServiceClient,
    scope_id: str,
    scope_type: str,
    role_definition_id: str,
) -> timedelta:
    """Return the maximum activation duration from the role-management policy."""
    DEFAULT_DURATION = timedelta(hours=8)
    try:
        odata_filter = (
            f"scopeId eq '{scope_id}' and scopeType eq '{scope_type}' "
            f"and roleDefinitionId eq '{role_definition_id}'"
        )
        from kiota_abstractions.base_request_configuration import RequestConfiguration
        from msgraph.generated.policies.role_management_policy_assignments.role_management_policy_assignments_request_builder import (
            RoleManagementPolicyAssignmentsRequestBuilder,
        )

        config = RequestConfiguration(
            query_parameters=RoleManagementPolicyAssignmentsRequestBuilder.RoleManagementPolicyAssignmentsRequestBuilderGetQueryParameters(
                filter=odata_filter,
            ),
        )

        policies = await client.policies.role_management_policy_assignments.get(
            request_configuration=config
        )

        if not policies or not policies.value:
            return DEFAULT_DURATION

        policy_id = policies.value[0].policy_id
        if not policy_id:
            return DEFAULT_DURATION

        rules = await client.policies.role_management_policies.by_unified_role_management_policy_id(
            policy_id
        ).rules.get()

        if not rules or not rules.value:
            return DEFAULT_DURATION

        for rule in rules.value:
            if rule.id == "Expiration_EndUser_Assignment":
                maximum_duration = getattr(rule, "maximum_duration", None)
                if maximum_duration and isinstance(maximum_duration, timedelta):
                    return maximum_duration
                break

        return DEFAULT_DURATION
    except Exception:
        return DEFAULT_DURATION


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
async def activate(
    name: str,
    justification: str,
    duration: int | None = None,
    access_id: str = "member",
    directory_scope_id: str = "/",
) -> ActivateResult:
    """Activate a PIM-eligible group or Entra role assignment.

    Specify group_name or role_name with a justification.

    Args:
        name: Name of the group or Entra role to activate (case-insensitive).
        justification: Reason for activating the assignment.
        duration: Duration in hours (defaults to policy maximum).
        access_id: Access relationship type for groups (default: "member").
        directory_scope_id: Directory scope for Entra roles (default: "/").
    """
    from kiota_abstractions.base_request_configuration import RequestConfiguration
    from msgraph.generated.identity_governance.privileged_access.group.eligibility_schedules.filter_by_current_user_with_on.filter_by_current_user_with_on_request_builder import (
        FilterByCurrentUserWithOnRequestBuilder as GroupEligFilterBuilder2,
    )
    from msgraph.generated.models.expiration_pattern import ExpirationPattern
    from msgraph.generated.models.expiration_pattern_type import ExpirationPatternType
    from msgraph.generated.models.privileged_access_group_assignment_schedule_request import (
        PrivilegedAccessGroupAssignmentScheduleRequest,
    )
    from msgraph.generated.models.privileged_access_group_relationships import (
        PrivilegedAccessGroupRelationships,
    )
    from msgraph.generated.models.request_schedule import RequestSchedule
    from msgraph.generated.models.schedule_request_actions import ScheduleRequestActions
    from msgraph.generated.models.unified_role_assignment_schedule_request import (
        UnifiedRoleAssignmentScheduleRequest,
    )
    from msgraph.generated.models.unified_role_schedule_request_actions import (
        UnifiedRoleScheduleRequestActions,
    )
    from msgraph.generated.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on.filter_by_current_user_with_on_request_builder import (
        FilterByCurrentUserWithOnRequestBuilder as RoleEligFilterBuilder2,
    )

    client = await get_client()

    # Fetch eligibility data to find the matching assignment
    group_elig_config = RequestConfiguration(
        query_parameters=GroupEligFilterBuilder2.FilterByCurrentUserWithOnRequestBuilderGetQueryParameters(
            expand=["group"],
        ),
    )
    role_elig_config = RequestConfiguration(
        query_parameters=RoleEligFilterBuilder2.FilterByCurrentUserWithOnRequestBuilderGetQueryParameters(
            expand=["roleDefinition"],
        ),
    )
    group_data, role_data = await asyncio.gather(
        client.identity_governance.privileged_access.group.eligibility_schedules.filter_by_current_user_with_on(
            "principal"
        ).get(request_configuration=group_elig_config),
        client.role_management.directory.role_eligibility_schedules.filter_by_current_user_with_on("principal").get(
            request_configuration=role_elig_config
        ),
    )

    name_lower = name.lower()

    # Search in group eligibilities
    for item in (group_data.value if group_data else []) or []:
        group = getattr(item, "group", None)
        display_name = getattr(group, "display_name", None) if group else None
        if display_name and display_name.lower() == name_lower:
            # Resolve access_id enum
            access_id_raw = item.access_id
            if access_id_raw is None:
                access_id_str = "member"
            elif hasattr(access_id_raw, "value"):
                access_id_str = str(access_id_raw.value)
            else:
                access_id_str = str(access_id_raw)

            group_id = item.group_id or ""

            # Look up the maximum duration from the policy
            max_dur = await _get_max_duration(client, group_id, "Group", access_id_str)
            act_duration = timedelta(hours=duration) if duration else max_dur

            # Get current user ID
            me = await client.me.get()
            if not me or not me.id:
                raise RuntimeError("Failed to retrieve current user identity.")

            # Resolve access_id for the request body
            if access_id.lower() == "owner":
                access_id_enum = PrivilegedAccessGroupRelationships.Owner
            else:
                access_id_enum = PrivilegedAccessGroupRelationships.Member

            body = PrivilegedAccessGroupAssignmentScheduleRequest(
                access_id=access_id_enum,
                principal_id=me.id,
                group_id=group_id,
                action=ScheduleRequestActions.SelfActivate,
                justification=justification,
                schedule_info=RequestSchedule(
                    expiration=ExpirationPattern(
                        type=ExpirationPatternType.AfterDuration,
                        duration=act_duration,
                    ),
                ),
            )

            await client.identity_governance.privileged_access.group.assignment_schedule_requests.post(body)

            return ActivateResult(
                message=f"Successfully activated group '{display_name}'",
                name=display_name,
                type="Group",
                duration=str(act_duration),
            )

    # Search in role eligibilities
    for item in (role_data.value if role_data else []) or []:
        role_def = item.role_definition
        display_name = role_def.display_name if role_def else None
        if display_name and display_name.lower() == name_lower:
            role_def_id = item.role_definition_id or ""

            max_dur = await _get_max_duration(
                client, directory_scope_id, "DirectoryRole", role_def_id
            )
            act_duration = timedelta(hours=duration) if duration else max_dur

            me = await client.me.get()
            if not me or not me.id:
                raise RuntimeError("Failed to retrieve current user identity.")

            body = UnifiedRoleAssignmentScheduleRequest(
                action=UnifiedRoleScheduleRequestActions.SelfActivate,
                principal_id=me.id,
                role_definition_id=role_def_id,
                directory_scope_id=directory_scope_id,
                justification=justification,
                schedule_info=RequestSchedule(
                    expiration=ExpirationPattern(
                        type=ExpirationPatternType.AfterDuration,
                        duration=act_duration,
                    ),
                ),
            )

            await client.role_management.directory.role_assignment_schedule_requests.post(body)

            return ActivateResult(
                message=f"Successfully activated role '{display_name}'",
                name=display_name,
                type="EntraRole",
                duration=str(act_duration),
            )

    raise ValueError(
        f"No eligible assignment found matching '{name}'. "
        "Use list_eligible to see available assignments."
    )


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
