# Entra PIM Codex Plugin

This plugin bundles the `entra-pim-mcp-server` MCP server with a Codex skill for Microsoft Entra Privileged Identity Management.

## Contents

- `.codex-plugin/plugin.json` declares the Codex plugin metadata.
- `.mcp.json` exposes the `entra-pim` MCP server through `uvx`.
- `skills/entra-pim/SKILL.md` provides Entra PIM usage guidance for Codex.

## Configuration

The MCP server requires `AZURE_TENANT_ID`. The plugin forwards that variable from the Codex process environment with `env_vars`; it does not hardcode a tenant ID because tenant selection is deployment-specific.

For Codex Desktop and the VS Code extension, shell environment variables may not be inherited. Put the tenant ID in `~/.codex/.env`, then restart Codex:

```shell
export AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
```

## Install

```bash
codex plugin marketplace add vexxhost/entra-pim-mcp-server --ref main
codex plugin add entra-pim@vexxhost-entra-pim
```
