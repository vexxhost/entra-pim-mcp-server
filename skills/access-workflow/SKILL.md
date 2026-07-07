---
name: access-workflow
description: Route Microsoft Entra PIM access requests through eligible assignment discovery, activation, and result reporting. Use when a user asks to inspect, choose, request, activate, or confirm privileged access through Entra PIM.
---

# Access Workflow

## Overview

Route Microsoft Entra PIM access requests through the right MCP-backed workflow. The MCP server carries the activation rules in its server instructions; keep this skill focused on selecting the workflow and presenting the result.

## Workflow

1. Use the Entra PIM MCP server for eligible assignment discovery, status checks, and activation requests.
2. Follow the server instructions returned by MCP initialization for activation safety and ambiguity handling.
3. Ask only for information that is missing from the user request or needed to choose between matching assignments.

## Output Conventions

- For listings, summarize assignment name, type, role, status, and expiry.
- For activation results, report assignment name, type, status, and activation duration when returned.
- Keep the final answer centered on access state and any remaining user action.

## Fallbacks

- If the server reports missing tenant configuration, tell the user to set `AZURE_TENANT_ID` where Codex can forward it to the MCP server.
- If browser sign-in is required, pause for the user to complete authentication before retrying.

## Reference

- The plugin MCP config forwards `AZURE_TENANT_ID` with `env_vars`; it does not hardcode tenant values.
