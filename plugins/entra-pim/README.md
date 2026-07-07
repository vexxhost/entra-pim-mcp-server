# Entra PIM Codex Plugin

This plugin bundles the `entra-pim-mcp-server` MCP server with a Codex skill for Microsoft Entra Privileged Identity Management.

## Contents

- `.codex-plugin/plugin.json` declares the Codex plugin metadata.
- `.mcp.json` exposes the `entra-pim` MCP server through `uvx`.
- `skills/entra-pim/SKILL.md` provides Entra PIM usage guidance for Codex.

## Configuration

The MCP server requires `AZURE_TENANT_ID` in the process environment used to launch Codex. The plugin does not include a tenant ID because tenant selection is deployment-specific.

## Install

```bash
codex plugin marketplace add vexxhost/entra-pim-mcp-server --ref main
codex plugin add entra-pim@vexxhost-entra-pim
```
