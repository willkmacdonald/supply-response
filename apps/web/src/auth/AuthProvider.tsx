import {InteractionRequiredAuthError, type AccountInfo, type AuthenticationResult} from "@azure/msal-browser";
import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode} from "react";
import {setAccessTokenProvider} from "../api";
import {createMsalClient, defaultEntraConfig, type EntraConfig} from "./msal";

export type AuthAccount = Pick<AccountInfo, "homeAccountId" | "name">;

export interface AuthClient {
  initialize(): Promise<void>;
  handleRedirectPromise(): Promise<{account: AuthAccount | null} | null>;
  getAllAccounts(): AuthAccount[];
  getActiveAccount(): AuthAccount | null;
  setActiveAccount(account: AuthAccount | null): void;
  loginRedirect(request: {scopes: string[]}): Promise<void>;
  acquireTokenSilent(request: {account: AuthAccount; scopes: string[]}): Promise<{accessToken: string}>;
  acquireTokenRedirect(request: {account: AuthAccount; scopes: string[]}): Promise<void>;
}

interface AuthContextValue {
  mode: "fallback" | "entra";
  account: AuthAccount | null;
  signIn(): Promise<void>;
  getAccessToken(): Promise<string | null>;
}

const fallbackValue: AuthContextValue = {
  mode: "fallback",
  account: null,
  signIn: async () => undefined,
  getAccessToken: async () => null,
};

const AuthContext = createContext<AuthContextValue>(fallbackValue);

function browserClient(config: EntraConfig): AuthClient {
  const client = createMsalClient(config);
  return {
    initialize: () => client.initialize(),
    handleRedirectPromise: () => client.handleRedirectPromise() as Promise<AuthenticationResult | null>,
    getAllAccounts: () => client.getAllAccounts(),
    getActiveAccount: () => client.getActiveAccount(),
    setActiveAccount: (account) => client.setActiveAccount(account as AccountInfo | null),
    loginRedirect: (request) => client.loginRedirect(request),
    acquireTokenSilent: (request) => client.acquireTokenSilent(request as {account: AccountInfo; scopes: string[]}),
    acquireTokenRedirect: (request) => client.acquireTokenRedirect(request as {account: AccountInfo; scopes: string[]}),
  };
}

export function AuthProvider({
  children,
  config = defaultEntraConfig,
  client: providedClient,
}: {
  children: ReactNode;
  config?: EntraConfig | null;
  client?: AuthClient;
}) {
  const client = useMemo(
    () => config ? providedClient ?? browserClient(config) : null,
    [config, providedClient],
  );
  const [account, setAccount] = useState<AuthAccount | null>(null);
  const [ready, setReady] = useState(config === null);
  const [authFailure, setAuthFailure] = useState(false);
  const interactiveRedirect = useRef<Promise<void> | null>(null);

  useEffect(() => {
    if (!client) return;
    setReady(false);
    setAuthFailure(false);
    let active = true;
    void (async () => {
      try {
        await client.initialize();
        const redirect = await client.handleRedirectPromise();
        const resolved = redirect?.account ?? client.getActiveAccount() ?? client.getAllAccounts()[0] ?? null;
        if (!active) return;
        client.setActiveAccount(resolved);
        setAccount(resolved);
        setReady(true);
      } catch {
        if (!active) return;
        setAuthFailure(true);
        setReady(false);
      }
    })();
    return () => { active = false; };
  }, [client]);

  const signIn = useCallback(async () => {
    if (!client || !config) return;
    setAuthFailure(false);
    if (!interactiveRedirect.current) {
      interactiveRedirect.current = client.loginRedirect({scopes: [config.apiScope]})
        .finally(() => { interactiveRedirect.current = null; });
    }
    await interactiveRedirect.current;
  }, [client, config]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!client || !config) return null;
    const active = account ?? client.getActiveAccount();
    if (!active) throw new Error("No authenticated Entra account is active");
    const request = {account: active, scopes: [config.apiScope]};
    try {
      return (await client.acquireTokenSilent(request)).accessToken;
    } catch (error) {
      if (!(error instanceof InteractionRequiredAuthError)) throw error;
      if (!interactiveRedirect.current) {
        interactiveRedirect.current = client.acquireTokenRedirect(request)
          .finally(() => { interactiveRedirect.current = null; });
      }
      await interactiveRedirect.current;
      return null;
    }
  }, [account, client, config]);

  useEffect(() => {
    setAccessTokenProvider(getAccessToken);
    return () => setAccessTokenProvider(async () => null);
  }, [getAccessToken]);

  const value = useMemo<AuthContextValue>(() => config ? {
    mode: "entra",
    account,
    signIn,
    getAccessToken,
  } : fallbackValue, [account, config, getAccessToken, signIn]);

  return <AuthContext.Provider value={value}>
    {authFailure
      ? <div role="alert">Secure sign-in failed. <button onClick={() => void signIn()}>Retry sign-in</button></div>
      : ready ? children : <p role="status">Completing secure sign-in…</p>}
  </AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
