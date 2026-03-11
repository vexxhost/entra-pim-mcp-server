import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { PrivilegedAccessGroupRelationships } from '@microsoft/msgraph-sdk/models/index.js';
import { Duration } from '@microsoft/kiota-abstractions';
import { getClient } from '../auth.js';

// OData filters don't support parameterized queries, so values are interpolated
// directly. All interpolated values originate from Graph API responses (UUIDs and
// well-known strings like 'member'/'owner'), not from user input.
async function getMaxDuration(
  client: import('@microsoft/msgraph-sdk').GraphServiceClient,
  filterStr: string,
): Promise<{ duration: string; warning?: string }> {
  const defaultDuration = 'PT8H';
  try {
    const policies = await client.policies.roleManagementPolicyAssignments.get({
      queryParameters: { filter: filterStr },
    });
    if (!policies?.value?.length)
      return { duration: defaultDuration, warning: 'No matching policy found; using default duration of 8 hours.' };

    const rules = await client.policies.roleManagementPolicies
      .byUnifiedRoleManagementPolicyId(policies.value[0].policyId!)
      .rules.get();

    for (const rule of rules?.value || []) {
      if (rule.id === 'Expiration_EndUser_Assignment') {
        const maxDur = (rule as { maximumDuration?: Duration }).maximumDuration;
        if (maxDur) return { duration: maxDur.toString() };
      }
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return {
      duration: defaultDuration,
      warning: `Failed to retrieve policy maximum duration (${detail}); using default of 8 hours.`,
    };
  }
  return { duration: defaultDuration };
}

export function registerActivateTool(server: McpServer): void {
  server.registerTool(
    'activate',
    {
      title: 'Activate privileged identity management assignment',
      description:
        'Activate a PIM assignment for a group or Entra role. Specify exactly one of: group_name, group_id, role_name, or role_id. If not authenticated, a browser window will open automatically for login.',
      inputSchema: {
        group_name: z
          .string()
          .optional()
          .describe('Name of the group to activate (mutually exclusive with group_id, role_name, role_id)'),
        group_id: z
          .string()
          .optional()
          .describe('ID of the group to activate (mutually exclusive with group_name, role_name, role_id)'),
        role_name: z
          .string()
          .optional()
          .describe(
            'Display name of the Entra role to activate (mutually exclusive with group_name, group_id, role_id)',
          ),
        role_id: z
          .string()
          .optional()
          .describe('ID of the Entra role to activate (mutually exclusive with group_name, group_id, role_name)'),
        justification: z.string().describe('Reason for activating the assignment'),
        duration: z.number().optional().describe('Duration in hours (defaults to policy maximum)'),
      },
      outputSchema: z.object({
        status: z.string(),
        warnings: z.array(z.string()).optional(),
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
          content: [
            {
              type: 'text' as const,
              text: 'Error: Specify exactly one of: group_name, group_id, role_name, or role_id.',
            },
          ],
          isError: true,
        };
      }

      try {
        const client = await getClient();
        const me = await client.me.get({ queryParameters: { select: ['id'] } });
        if (!me?.id) throw new Error('Failed to retrieve current user ID');
        const principalId = me.id;

        let status: string;
        const warnings: string[] = [];

        if (params.group_name || params.group_id) {
          let groupId: string;
          let accessId: string = 'member';

          const eligible = await client.identityGovernance.privilegedAccess.group.eligibilitySchedules
            .filterByCurrentUserWithOn('principal')
            .get({ queryParameters: { expand: ['group'] } });

          if (params.group_id) {
            groupId = params.group_id;
            const match = (eligible?.value || []).find((item) => item.groupId === params.group_id);
            if (!match) throw new Error(`No eligible group assignment found with ID "${params.group_id}"`);
            accessId = match.accessId || 'member';
          } else {
            // Cast needed: preview Graph SDK doesn't fully type the `group` navigation property
            const match = (eligible?.value || []).find(
              (item) =>
                ((item.group as { displayName?: string })?.displayName || '').toLowerCase() ===
                params.group_name!.toLowerCase(),
            );
            if (!match) throw new Error(`No eligible group assignment found with name "${params.group_name}"`);
            if (!match.groupId) throw new Error(`Eligible group assignment for "${params.group_name}" has no group ID`);
            groupId = match.groupId;
            accessId = match.accessId || 'member';
          }

          const { duration: durationStr, warning: durationWarning } = params.duration
            ? { duration: `PT${params.duration}H` }
            : await getMaxDuration(
                client,
                `scopeId eq '${groupId}' and scopeType eq 'Group' and roleDefinitionId eq '${accessId}'`,
              );
          if (durationWarning) warnings.push(durationWarning);

          const result = await client.identityGovernance.privilegedAccess.group.assignmentScheduleRequests.post({
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
            const eligible = await client.roleManagement.directory.roleEligibilitySchedules
              .filterByCurrentUserWithOn('principal')
              .get();
            const match = (eligible?.value || []).find((item) => item.roleDefinitionId === roleId);
            if (match?.directoryScopeId) scopeId = match.directoryScopeId;
          } else {
            const eligible = await client.roleManagement.directory.roleEligibilitySchedules
              .filterByCurrentUserWithOn('principal')
              .get({ queryParameters: { expand: ['roleDefinition'] } });

            const match = (eligible?.value || []).find(
              (item) => (item.roleDefinition?.displayName || '').toLowerCase() === params.role_name!.toLowerCase(),
            );
            if (!match) throw new Error(`No eligible role assignment found with name "${params.role_name}"`);
            if (!match.roleDefinitionId)
              throw new Error(`Eligible role assignment for "${params.role_name}" has no role definition ID`);
            roleId = match.roleDefinitionId;
            scopeId = match.directoryScopeId || '/';
          }

          const { duration: durationStr, warning: durationWarning } = params.duration
            ? { duration: `PT${params.duration}H` }
            : await getMaxDuration(
                client,
                `scopeId eq '${scopeId}' and scopeType eq 'DirectoryRole' and roleDefinitionId eq '${roleId}'`,
              );
          if (durationWarning) warnings.push(durationWarning);

          const result = await client.roleManagement.directory.roleAssignmentScheduleRequests.post({
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

        const result_data = { status, ...(warnings.length ? { warnings } : {}) };
        return {
          structuredContent: result_data,
          content: [{ type: 'text' as const, text: JSON.stringify(result_data) }],
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
