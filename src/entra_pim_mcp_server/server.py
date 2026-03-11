"""Entra PIM MCP Server — list and activate Azure PIM assignments."""

import asyncio
import os
import sys
from pathlib import Path

from azure.identity import (
    AuthenticationRecord,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
)
from mcp.server.fastmcp import FastMCP
from msgraph import GraphServiceClient
from platformdirs import user_config_dir

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


mcp = FastMCP("entra-pim-mcp-server")


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
