#!/usr/bin/env npx tsx
/**
 * Test script that uses the production getClient() and tests all Graph API calls.
 * Usage: AZURE_TENANT_ID=xxx AZURE_CLIENT_ID=yyy npx tsx test-api.ts
 */

import { getClient } from './src/auth.js';

const client = await getClient();
console.log('Client ready (token cached)');

// Test 1: Get current user
console.log('\n=== Test: Get Current User ===');
const me = await client.me.get({ queryParameters: { select: ['id', 'displayName'] } });
console.log(`User: ${me?.displayName} (${me?.id})`);

// Test 2: Group eligible assignments with $expand=group
console.log('\n=== Test: Group Eligible Assignments ===');
const groupData = await client.identityGovernance.privilegedAccess.group
  .eligibilitySchedules.filterByCurrentUserWithOn('principal')
  .get({ queryParameters: { expand: ['group'] } });
const groupItems = groupData?.value || [];
console.log(`Found ${groupItems.length} group eligible assignments`);
for (const item of groupItems) {
  const name = (item.group as { displayName?: string })?.displayName || item.groupId;
  console.log(`  - ${name} (${item.accessId}, ${item.memberType})`);
}

// Test 3: Group active assignments
console.log('\n=== Test: Group Active Assignments ===');
const groupActive = await client.identityGovernance.privilegedAccess.group
  .assignmentScheduleInstances.filterByCurrentUserWithOn('principal').get();
console.log(`Found ${groupActive?.value?.length || 0} active group assignments`);

// Test 4: Role eligible assignments with $expand=roleDefinition
console.log('\n=== Test: Role Eligible Assignments ===');
const roleData = await client.roleManagement.directory
  .roleEligibilitySchedules.filterByCurrentUserWithOn('principal')
  .get({ queryParameters: { expand: ['roleDefinition'] } });
console.log(`Found ${roleData?.value?.length || 0} role eligible assignments`);

// Test 5: Role active assignments
console.log('\n=== Test: Role Active Assignments ===');
const roleActive = await client.roleManagement.directory
  .roleAssignmentScheduleInstances.filterByCurrentUserWithOn('principal').get();
console.log(`Found ${roleActive?.value?.length || 0} active role assignments`);

console.log('\n✅ All tests passed!');
