import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getClient } from '../auth.js';

export function registerListEligibleTool(server: McpServer): void {
  server.registerTool(
    'list_eligible',
    {
      title: 'List Eligible Privileged Identity Management Assignments',
      description: 'List all eligible Privileged Identity Management (PIM) assignments (Group and Entra Role) for the authenticated user. If not authenticated, a browser window will open automatically for login.',
      outputSchema: z.object({
        assignments: z.array(z.object({
          type: z.enum(['Group', 'EntraRole']),
          name: z.string(),
          id: z.string(),
          role: z.string(),
          memberType: z.string(),
          endTime: z.string(),
          status: z.enum(['Active', 'Eligible']),
        })),
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      try {
        const client = await getClient();

        const [groupData, groupActive, roleData, roleActive] = await Promise.all([
          client.identityGovernance.privilegedAccess.group
            .eligibilitySchedules.filterByCurrentUserWithOn('principal')
            .get({ queryParameters: { expand: ['group'] } }),
          client.identityGovernance.privilegedAccess.group
            .assignmentScheduleInstances.filterByCurrentUserWithOn('principal')
            .get(),
          client.roleManagement.directory
            .roleEligibilitySchedules.filterByCurrentUserWithOn('principal')
            .get({ queryParameters: { expand: ['roleDefinition'] } }),
          client.roleManagement.directory
            .roleAssignmentScheduleInstances.filterByCurrentUserWithOn('principal')
            .get(),
        ]);

        const activeGroupIds = new Set((groupActive?.value || []).map(a => `${a.groupId}:${a.accessId}`));
        const activeRoleIds = new Set((roleActive?.value || []).map(a => a.roleDefinitionId));

        const groups = (groupData?.value || []).map(item => ({
          type: 'Group' as const,
          name: (item.group as { displayName?: string })?.displayName || item.groupId || '',
          id: item.groupId || '',
          role: item.accessId || '',
          memberType: item.memberType || '',
          endTime: item.scheduleInfo?.expiration?.endDateTime?.toISOString() || 'N/A',
          status: activeGroupIds.has(`${item.groupId}:${item.accessId}`) ? 'Active' as const : 'Eligible' as const,
        }));

        const roles = (roleData?.value || []).map(item => ({
          type: 'EntraRole' as const,
          name: item.roleDefinition?.displayName || item.roleDefinitionId || '',
          id: item.roleDefinitionId || '',
          role: item.roleDefinition?.displayName || item.roleDefinitionId || '',
          memberType: 'Direct',
          endTime: item.scheduleInfo?.expiration?.endDateTime?.toISOString() || 'N/A',
          status: activeRoleIds.has(item.roleDefinitionId || '') ? 'Active' as const : 'Eligible' as const,
        }));

        const assignments = [...groups, ...roles];

        return {
          structuredContent: { assignments },
          content: [{ type: 'text' as const, text: JSON.stringify({ assignments }) }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: 'text' as const, text: `Error listing eligible assignments: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
