#!/usr/bin/env node

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { registerListEligibleTool } from './tools/list-eligible.js';
import { registerActivateTool } from './tools/activate.js';

const AZURE_TENANT_ID = process.env.AZURE_TENANT_ID;
const AZURE_CLIENT_ID = process.env.AZURE_CLIENT_ID;

if (!AZURE_TENANT_ID || !AZURE_CLIENT_ID) {
  console.error('Error: AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required.');
  process.exit(1);
}

const server = new McpServer({
  name: 'entra-pim-mcp-server',
  version: '0.1.0',
});

registerListEligibleTool(server);
registerActivateTool(server);

const transport = new StdioServerTransport();
await server.connect(transport);
