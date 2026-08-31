import {
  BrowserCacheLocation,
  PublicClientApplication,
  type Configuration,
} from "@azure/msal-browser";

export interface EntraConfig {
  tenantId: string;
  webClientId: string;
  apiScope: string;
  redirectUri: string;
}

type EntraEnvironment = Partial<Record<
  | "VITE_ENTRA_TENANT_ID"
  | "VITE_ENTRA_WEB_CLIENT_ID"
  | "VITE_ENTRA_API_SCOPE"
  | "VITE_ENTRA_REDIRECT_URI",
  string
>>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function readEntraConfig(env: EntraEnvironment): EntraConfig | null {
  const values = [
    env.VITE_ENTRA_TENANT_ID,
    env.VITE_ENTRA_WEB_CLIENT_ID,
    env.VITE_ENTRA_API_SCOPE,
    env.VITE_ENTRA_REDIRECT_URI,
  ].map((value) => value?.trim() || undefined);
  if (values.every((value) => value === undefined)) return null;
  if (values.some((value) => value === undefined)) {
    throw new Error("Entra mode requires all four tenant/client/scope/redirect settings");
  }
  const [tenantId, webClientId, apiScope, redirectUri] = values as [string, string, string, string];
  if (!UUID.test(tenantId) || !UUID.test(webClientId)) {
    throw new Error("Entra tenant and web client settings must be UUIDs");
  }
  const scopeMatch = /^api:\/\/([^/]+)\/access_as_user$/i.exec(apiScope);
  if (!scopeMatch || !UUID.test(scopeMatch[1])) {
    throw new Error("Entra API scope must be the exact access_as_user scope URI");
  }
  const redirect = new URL(redirectUri);
  const isLocalhost = redirect.protocol === "http:" && ["localhost", "127.0.0.1"].includes(redirect.hostname);
  if ((redirect.protocol !== "https:" && !isLocalhost) || redirect.search || redirect.hash) {
    throw new Error("Entra redirect URI must be exact HTTPS or loopback HTTP without query/fragment");
  }
  const normalizedInput = redirectUri.replace(/\/$/, "");
  const canonicalRedirect = redirect.toString().replace(/\/$/, "");
  if (normalizedInput !== canonicalRedirect) {
    throw new Error("Entra redirect URI must use a canonical authority");
  }
  return {tenantId, webClientId, apiScope, redirectUri: canonicalRedirect};
}

export function createMsalConfig(config: EntraConfig): Configuration {
  return {
    auth: {
      clientId: config.webClientId,
      authority: `https://login.microsoftonline.com/${config.tenantId}`,
      redirectUri: config.redirectUri,
    },
    cache: {
      // Redirect flows require browser-backed transient state. Session storage
      // keeps tokens out of localStorage and clears them when the tab closes.
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
    system: {allowPlatformBroker: false},
  };
}

export const defaultEntraConfig = readEntraConfig(import.meta.env as EntraEnvironment);

export function createMsalClient(config: EntraConfig): PublicClientApplication {
  return new PublicClientApplication(createMsalConfig(config));
}
