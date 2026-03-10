import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { PrivilegedAccessGroupRelationships } from '@microsoft/msgraph-sdk/models/index.js';
import { Duration } from '@microsoft/kiota-abstractions';
import { getClient } from '../auth.js';

async function getMaxDuration(
  client: import('@microsoft/msgraph-sdk').GraphServiceClient,
  filterStr: string,
): Promise<string> {
  const defaultDuration = 'PT8H';
  try {
    const policies = await client.policies.roleManagementPolicyAssignments
      .get({ queryParameters: { filter: filterStr } });
    if (!policies?.value?.length) return defaultDuration;

    const rules = await client.policies
      .roleManagementPolicies.byUnifiedRoleManagementPolicyId(policies.value[0].policyId!)
      .rules.get();

    for (const rule of rules?.value || []) {
      if (rule.id === 'Expiration_EndUser_Assignment') {
        const maxDur = (rule as { maximumDuration?: Duration }).maximumDuration;
        if (maxDur) return maxDur.toString();
      }
    }
  } catch {
    // Fall through to default
  }
  return defaultDuration;
}

const activateOutputSchema = z.object({
  status: z.string(),
});

export function registerActivateTool(server: McpServer): void {
  server.registerTool(
    'activate',
    {
      title: 'Activate Privileged Identity Management Assignment',
      description: 'Activate a PIM assignment for a group or Entra role. Specify exactly one of: group_name, group_id, role_name, or role_id. If not authenticated, a browser window will open automatically for login.',
      inputSchema: {
        group_name: z.string().optional().describe('Name of the group to activate (mutually exclusive with group_id, role_name, role_id)'),
        group_id: z.string().optional().describe('ID of the group to activate (mutually exclusive with group_name, role_name, role_id)'),
        role_name: z.string().optional().describe('Display name of the Entra role to activate (mutually exclusive with group_name, group_id, role_id)'),
        role_id: z.string().optional().describe('ID of the Entra role to activate (mutually exclusive with group_name, group_id, role_name)'),
        justification: z.string().describe('Reason for activating the assignment'),
        duration: z.number().optional().describe('Duration in hours (defaults to policy maximum)'),
      },
      outputSchema: z.object({
        status: z.string(),
      }),
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (params) => {
      const identifiers = [params.group_name, params.group_id, params.role_name, params.role_id].filter(Boolean);
      if (identifiers.length !== 1) {
        return {
          content: [{ type: 'text' as const, text: 'Error: Specify exactly one of: group_name, group_id, role_name, or role_id.' }],
          isError: true,
        };
      }

      try {
        const client = await getClient();
        const me = await client.me.get({ queryParameters: { select: ['id'] } });
        const principalId = me!.id!;

        let status: string;

        if (params.group_name || params.group_id) {
          let groupId: string;
          let accessId: string = 'member';

          if (params.group_id) {
            groupId = params.group_id;
          } else {
            const eligible = await client.identityGovernance.privilegedAccess.group
              .eligibilitySchedules.filterByCurrentUserWithOn('principal')
              .get({ queryParameters: { expand: ['group'] } });

            const match = (eligible?.value || []).find(
              item => ((item.group as { displayName?: string })?.displayName || '').toLowerCase() === params.group_name!.toLowerCase(),
            );
            if (!match) throw new Error(`No eligible group assignment found with name "${params.group_name}"`);
            groupId = match.groupId!;
            accessId = match.accessId || 'member';
          }

          const durationStr = params.duration
            ? `PT${params.duration}H`
            : await getMaxDuration(client, `scopeId eq '${groupId}' and scopeType eq 'Group' and roleDefinitionId eq 'member'`);

          const result = await client.identityGovernance.privilegedAccess.group
            .assignmentScheduleRequests.post({
              action: 'selfActivate',
              principalId,
              groupId,
              accessId: accessId as PrivilegedAccessGroupRelationships,
              justification: params.justification,
              scheduleInfo: {
                startDateTime: new Date(),
                expiration: {
                  type: 'afterDuration',
                  duration: Duration.parse(durationStr) ?? new Duration({ hours: 8 }),
                },
              },
            });

          status = result?.status || 'Pending';
        } else {
          let roleId: string;
          let scopeId = '/';

          if (params.role_id) {
            roleId = params.role_id;
            const eligible = await client.roleManagement.directory
              .roleEligibilitySchedules.filterByCurrentUserWithOn('principal').get();
            const match = (eligible?.value || []).find(item => item.roleDefinitionId === roleId);
            if (match?.directoryScopeId) scopeId = match.directoryScopeId;
          } else {
            const eligible = await client.roleManagement.directory
              .roleEligibilitySchedules.filterByCurrentUserWithOn('principal')
              .get({ queryParameters: { expand: ['roleDefinition'] } });

            const match = (eligible?.value || []).find(
              item => (item.roleDefinition?.displayName || '').toLowerCase() === params.role_name!.toLowerCase(),
            );
            if (!match) throw new Error(`No eligible role assignment found with name "${params.role_name}"`);
            roleId = match.roleDefinitionId!;
            scopeId = match.directoryScopeId || '/';
          }

          const durationStr = params.duration
            ? `PT${params.duration}H`
            : await getMaxDuration(client, `scopeId eq '${scopeId}' and scopeType eq 'DirectoryRole' and roleDefinitionId eq '${roleId}'`);

          const result = await client.roleManagement.directory
            .roleAssignmentScheduleRequests.post({
              action: 'selfActivate',
              principalId,
              roleDefinitionId: roleId,
              directoryScopeId: scopeId,
              justification: params.justification,
              scheduleInfo: {
                startDateTime: new Date(),
                expiration: {
                  type: 'afterDuration',
                  duration: Duration.parse(durationStr) ?? new Duration({ hours: 8 }),
                },
              },
            });

          status = result?.status || 'Pending';
        }

        return {
          structuredContent: { status },
          content: [{ type: 'text' as const, text: JSON.stringify({ status }) }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: 'text' as const, text: `Error activating assignment: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
