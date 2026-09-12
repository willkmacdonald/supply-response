import {type AccountInfo, type AuthenticationResult} from "@azure/msal-browser";
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
  loginRedirect(request: {scopes: string[]; redirectStartPage?: string}): Promise<void>;
  acquireTokenSilent(request: {account: AuthAccount; scopes: string[]}): Promise<{accessToken: string}>;
  acquireTokenRedirect(request: {account: AuthAccount; scopes: string[]; redirectStartPage?: string}): Promise<void>;
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

export class AuthRecoveryRequiredError extends Error {
  constructor() {
    super("Authentication recovery is required");
    this.name = "AuthRecoveryRequiredError";
  }
}

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
  const [authRecovery, setAuthRecovery] = useState(false);
  const recoveryRequired = useRef(false);
  const activeAccount = useRef<AuthAccount | null>(null);
  const interactiveRedirect = useRef<Promise<void> | null>(null);
  const initializationAttempt = useRef(0);

  const initializeAuth = useCallback(async () => {
    if (!client) return;
    const attempt = ++initializationAttempt.current;
    setReady(false);
    setAuthFailure(false);
    try {
      await client.initialize();
      const redirect = await client.handleRedirectPromise();
      const resolved = redirect?.account ?? client.getActiveAccount() ?? client.getAllAccounts()[0] ?? null;
      if (attempt !== initializationAttempt.current) return;
      client.setActiveAccount(resolved);
      activeAccount.current = resolved;
      setAccount(resolved);
      recoveryRequired.current = false;
      setAuthRecovery(false);
      setReady(true);
    } catch {
      if (attempt !== initializationAttempt.current) return;
      setAuthFailure(true);
      setReady(false);
    }
  }, [client]);

  useEffect(() => {
    if (!client) return;
    void initializeAuth();
    return () => { initializationAttempt.current += 1; };
  }, [client, initializeAuth]);

  const signIn = useCallback(async () => {
    if (!client || !config) return;
    setAuthFailure(false);
    try {
      if (!interactiveRedirect.current) {
        interactiveRedirect.current = client.loginRedirect({
          scopes: [config.apiScope],
          redirectStartPage: window.location.href,
        })
          .finally(() => { interactiveRedirect.current = null; });
      }
      await interactiveRedirect.current;
    } catch {
      setAuthFailure(true);
      setReady(false);
    }
  }, [client, config]);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!client || !config) return null;
    if (recoveryRequired.current) throw new AuthRecoveryRequiredError();
    const active = activeAccount.current ?? client.getActiveAccount();
    if (!active) {
      recoveryRequired.current = true;
      setAuthRecovery(true);
      throw new AuthRecoveryRequiredError();
    }
    const request = {account: active, scopes: [config.apiScope]};
    try {
      const token = (await client.acquireTokenSilent(request)).accessToken;
      if (recoveryRequired.current) throw new AuthRecoveryRequiredError();
      return token;
    } catch {
      recoveryRequired.current = true;
      setAuthRecovery(true);
      throw new AuthRecoveryRequiredError();
    }
  }, [client, config]);

  const recoverSignIn = useCallback(async () => {
    if (!client || !config) return;
    if (!interactiveRedirect.current) {
      const active = account ?? client.getActiveAccount();
      const redirectStartPage = window.location.href;
      const request = {scopes: [config.apiScope], redirectStartPage};
      interactiveRedirect.current = (active
        ? client.acquireTokenRedirect({...request, account: active})
        : client.loginRedirect(request)
      ).finally(() => { interactiveRedirect.current = null; });
    }
    try {
      await interactiveRedirect.current;
    } catch {
      recoveryRequired.current = true;
      setAuthRecovery(true);
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
      ? <div role="alert">Secure sign-in failed. <button onClick={() => void initializeAuth()}>Retry sign-in</button></div>
      : ready ? <>
        {authRecovery && <div className="auth-recovery" role="alert" aria-label="Sign-in required">
          We couldn't renew your sign-in. Sign in again to continue.{" "}
          <button onClick={() => void recoverSignIn()}>Sign in again</button>
        </div>}
        <div hidden={authRecovery} inert={authRecovery ? true : undefined} aria-hidden={authRecovery || undefined}>{children}</div>
      </> : <p role="status">Completing secure sign-in…</p>}
  </AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
