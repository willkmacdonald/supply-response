export interface EntraConfig {
  tenantId: string;
  webClientId: string;
  apiScope: string;
  redirectUri: string;
}

type Persona = "alex" | "taylor";

const personaKey = "supply-response-e2e-persona";
const requestedPersona = new URLSearchParams(window.location.search).get("e2ePersona");
if (requestedPersona === "alex" || requestedPersona === "taylor") {
  window.sessionStorage.setItem(personaKey, requestedPersona);
}

const configured = window.sessionStorage.getItem(personaKey) !== null;
const config: EntraConfig = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  webClientId: "22222222-2222-4222-8222-222222222222",
  apiScope: "api://33333333-3333-4333-8333-333333333333/access_as_user",
  redirectUri: "http://127.0.0.1:5173/auth/callback",
};

export const defaultEntraConfig = configured ? config : null;

function currentPersona(): Persona {
  return window.sessionStorage.getItem(personaKey) === "taylor" ? "taylor" : "alex";
}

function account() {
  const persona = currentPersona();
  return {homeAccountId: persona, name: persona === "taylor" ? "Taylor" : "Alex"};
}

export function createMsalClient(_config: EntraConfig) {
  return {
    initialize: async () => undefined,
    handleRedirectPromise: async () => null,
    getAllAccounts: () => [account()],
    getActiveAccount: () => account(),
    setActiveAccount: () => undefined,
    loginRedirect: async (request: {redirectStartPage?: string; prompt?: "select_account"}) => {
      if (request.prompt !== "select_account") return;
      const next = currentPersona() === "alex" ? "taylor" : "alex";
      window.sessionStorage.setItem(personaKey, next);
      const url = new URL(request.redirectStartPage ?? window.location.href);
      url.searchParams.set("e2ePersona", next);
      window.location.assign(url);
      await new Promise<void>(() => undefined);
    },
    acquireTokenSilent: async () => ({accessToken: "mocked-e2e-token"}),
    acquireTokenRedirect: async () => undefined,
  };
}
