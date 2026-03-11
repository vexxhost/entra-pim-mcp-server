"""Entra PIM MCP Server — list and activate Azure PIM assignments."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("entra-pim-mcp-server")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
