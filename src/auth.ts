import { useIdentityPlugin, InteractiveBrowserCredential, type AuthenticationRecord } from '@azure/identity';
import { cachePersistencePlugin } from '@azure/identity-cache-persistence';
import { AzureIdentityAuthenticationProvider } from '@microsoft/kiota-authentication-azure';
import { createGraphServiceClient, GraphRequestAdapter, type GraphServiceClient } from '@microsoft/msgraph-sdk';
import '@microsoft/msgraph-sdk-users';
import '@microsoft/msgraph-sdk-identitygovernance';
import '@microsoft/msgraph-sdk-rolemanagement';
import '@microsoft/msgraph-sdk-policies';
import { readFile, writeFile, mkdir } from 'fs/promises';
import envPaths from 'env-paths';
import { Agent, setGlobalDispatcher } from 'undici';

useIdentityPlugin(cachePersistencePlugin);

// Node.js v24+ adds Accept-Language: * per WHATWG Fetch spec step 16.
// Graph PIM endpoints reject it with CultureNotFoundException.
// Use an undici interceptor to replace the default with en-US.
setGlobalDispatcher(new Agent().compose(function (dispatch) {
  return function (opts, handler) {
    const h = opts.headers as Record<string, string> | undefined;
    if (h && typeof h === 'object' && !Array.isArray(h)) {
      if (h['accept-language'] === '*') {
        h['accept-language'] = 'en-US';
      }
    }
    return dispatch(opts, handler);
  };
}));

const GRAPH_SCOPES = [
  'User.Read',
  'Group.Read.All',
  'PrivilegedAssignmentSchedule.ReadWrite.AzureADGroup',
  'PrivilegedEligibilitySchedule.Read.AzureADGroup',
  'RoleManagementPolicy.Read.AzureADGroup',
  'RoleEligibilitySchedule.Read.Directory',
  'RoleAssignmentSchedule.ReadWrite.Directory',
  'RoleManagementPolicy.Read.Directory',
];

const paths = envPaths('entra-pim-mcp-server');
const AUTH_RECORD_PATH = `${paths.config}/auth-record.json`;

async function loadAuthRecord(): Promise<AuthenticationRecord | undefined> {
  try {
    return JSON.parse(await readFile(AUTH_RECORD_PATH, 'utf-8'));
  } catch {
    return undefined;
  }
}

async function saveAuthRecord(record: AuthenticationRecord): Promise<void> {
  await mkdir(paths.config, { recursive: true });
  await writeFile(AUTH_RECORD_PATH, JSON.stringify(record));
}

let clientPromise: Promise<GraphServiceClient> | null = null;

export function getClient(): Promise<GraphServiceClient> {
  if (!clientPromise) {
    clientPromise = initClient();
  }
  return clientPromise;
}

async function initClient(): Promise<GraphServiceClient> {
  const tenantId = process.env.AZURE_TENANT_ID;
  const clientId = process.env.AZURE_CLIENT_ID;

  if (!tenantId || !clientId) {
    throw new Error('AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables are required.');
  }

  const authRecord = await loadAuthRecord();

  const credential = new InteractiveBrowserCredential({
    tenantId,
    clientId,
    redirectUri: 'http://localhost',
    authenticationRecord: authRecord,
    tokenCachePersistenceOptions: {
      enabled: true,
      name: 'entra-pim-mcp-server',
      unsafeAllowUnencryptedStorage: true,
    },
  });

  // authenticate() does silent auth if possible, interactive only on first run
  const record = await credential.authenticate(GRAPH_SCOPES);
  if (record) {
    await saveAuthRecord(record);
  }

  const authProvider = new AzureIdentityAuthenticationProvider(credential, GRAPH_SCOPES);
  const requestAdapter = new GraphRequestAdapter(authProvider);
  return createGraphServiceClient(requestAdapter);
}
