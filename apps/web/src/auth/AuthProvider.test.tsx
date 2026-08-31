// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {BrowserCacheLocation, InteractionRequiredAuthError} from "@azure/msal-browser";
import {act, cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, describe, expect, it, vi} from "vitest";
import {AuthProvider, type AuthClient, useAuth} from "./AuthProvider";
import {createMsalConfig, readEntraConfig} from "./msal";

const entraConfig = {
  tenantId: "11111111-1111-4111-8111-111111111111",
  webClientId: "22222222-2222-4222-8222-222222222222",
  apiScope: "api://33333333-3333-4333-8333-333333333333/access_as_user",
  redirectUri: "http://localhost:5173/auth/callback",
};

function Consumer() {
  const auth = useAuth();
  return <div>
    <span data-testid="mode">{auth.mode}</span>
    <span data-testid="name">{auth.account?.name ?? "anonymous"}</span>
    <button onClick={() => void auth.signIn()}>Sign in</button>
    <button onClick={() => void auth.getAccessToken().then((token) => {
      document.body.dataset.token = token ?? "none";
    })}>Get token</button>
  </div>;
}

function fakeClient(): AuthClient {
  return {
    initialize: vi.fn().mockResolvedValue(undefined),
    handleRedirectPromise: vi.fn().mockResolvedValue(null),
    getAllAccounts: vi.fn().mockReturnValue([{homeAccountId: "alex", name: "Alex Morgan"}]),
    getActiveAccount: vi.fn().mockReturnValue(null),
    setActiveAccount: vi.fn(),
    loginRedirect: vi.fn().mockResolvedValue(undefined),
    acquireTokenSilent: vi.fn().mockResolvedValue({accessToken: "dynamic-api-token"}),
    acquireTokenRedirect: vi.fn().mockResolvedValue(undefined),
  };
}

afterEach(() => {
  cleanup();
  delete document.body.dataset.token;
});

describe("Entra configuration", () => {
  it("requires an exact all-or-nothing tenant/client/scope/redirect configuration", () => {
    expect(() => readEntraConfig({VITE_ENTRA_TENANT_ID: entraConfig.tenantId}))
      .toThrow(/all four/);
    expect(() => readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: "api://------------------------------------/access_as_user",
      VITE_ENTRA_REDIRECT_URI: entraConfig.redirectUri,
    })).toThrow(/scope/);
    expect(readEntraConfig({})).toBeNull();
    expect(readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: entraConfig.apiScope,
      VITE_ENTRA_REDIRECT_URI: entraConfig.redirectUri,
    })).toEqual(entraConfig);
  });

  it.each([
    "https://example.com/callback?next=1",
    "https://example.com/callback#fragment",
    "http://example.com/callback",
  ])("rejects a non-exact redirect URI: %s", (redirectUri) => {
    expect(() => readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: entraConfig.apiScope,
      VITE_ENTRA_REDIRECT_URI: redirectUri,
    })).toThrow(/redirect/);
  });

  it("normalizes only a single trailing slash", () => {
    expect(readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: entraConfig.apiScope,
      VITE_ENTRA_REDIRECT_URI: "https://example.com/auth/callback/",
    })?.redirectUri).toBe("https://example.com/auth/callback");
  });

  it.each([
    "https://EXAMPLE.com/auth/callback/",
    "https://example.com:443/auth/callback/",
    "http://localhost:80/auth/callback/",
  ])("rejects a redirect authority that URL would canonicalize: %s", (redirectUri) => {
    expect(() => readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: entraConfig.apiScope,
      VITE_ENTRA_REDIRECT_URI: redirectUri,
    })).toThrow(/canonical/);
  });

  it.each([
    "https://example.com/a/../auth/callback",
    "https://example.com/./auth/callback",
    "https://example.com/a/%2e%2e/auth/callback",
  ])("rejects a redirect path that URL would canonicalize: %s", (redirectUri) => {
    expect(() => readEntraConfig({
      VITE_ENTRA_TENANT_ID: entraConfig.tenantId,
      VITE_ENTRA_WEB_CLIENT_ID: entraConfig.webClientId,
      VITE_ENTRA_API_SCOPE: entraConfig.apiScope,
      VITE_ENTRA_REDIRECT_URI: redirectUri,
    })).toThrow(/canonical/);
  });

  it("uses the tenant-specific authority and never localStorage", () => {
    const config = createMsalConfig(entraConfig);
    expect(config.auth).toMatchObject({
      clientId: entraConfig.webClientId,
      authority: `https://login.microsoftonline.com/${entraConfig.tenantId}`,
      redirectUri: entraConfig.redirectUri,
    });
    expect(config.cache?.cacheLocation).toBe(BrowserCacheLocation.SessionStorage);
    expect(config.cache?.cacheLocation).not.toBe(BrowserCacheLocation.LocalStorage);
  });
});

describe("AuthProvider", () => {
  it("keeps fallback browser tests operational without Entra", async () => {
    render(<AuthProvider config={null}><Consumer /></AuthProvider>);
    expect(screen.getByTestId("mode")).toHaveTextContent("fallback");
    await userEvent.click(screen.getByRole("button", {name: "Get token"}));
    expect(document.body.dataset.token).toBe("none");
  });

  it("handles redirect state and acquires API tokens silently", async () => {
    const client = fakeClient();
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId("name")).toHaveTextContent("Alex Morgan"));
    expect(client.initialize).toHaveBeenCalledOnce();
    expect(client.handleRedirectPromise).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", {name: "Get token"}));
    await waitFor(() => expect(document.body.dataset.token).toBe("dynamic-api-token"));
    expect(client.acquireTokenSilent).toHaveBeenCalledWith({
      account: expect.objectContaining({homeAccountId: "alex"}),
      scopes: [entraConfig.apiScope],
    });
  });

  it("starts sign-in using redirect with only the API scope", async () => {
    const client = fakeClient();
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("mode")).toHaveTextContent("entra"));
    await userEvent.click(screen.getByRole("button", {name: "Sign in"}));
    expect(client.loginRedirect).toHaveBeenCalledWith({scopes: [entraConfig.apiScope]});
  });

  it("does not mount API-consuming children before redirect initialization", async () => {
    let resolveInitialization!: () => void;
    const client = fakeClient();
    client.initialize = vi.fn(() => new Promise<void>((resolve) => {
      resolveInitialization = resolve;
    }));

    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    expect(screen.queryByRole("button", {name: "Get token"})).not.toBeInTheDocument();
    await act(async () => resolveInitialization());
    await waitFor(() => expect(screen.getByRole("button", {name: "Get token"})).toBeInTheDocument());
  });

  it("retries initialization and redirect handling after an initial failure", async () => {
    const client = fakeClient();
    client.initialize = vi.fn()
      .mockRejectedValueOnce(new Error("initialization failed"))
      .mockResolvedValueOnce(undefined);
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent(/secure sign-in failed/i);
    await userEvent.click(screen.getByRole("button", {name: /retry sign-in/i}));
    await waitFor(() => expect(screen.getByTestId("name")).toHaveTextContent("Alex Morgan"));
    expect(client.initialize).toHaveBeenCalledTimes(2);
    expect(client.handleRedirectPromise).toHaveBeenCalledOnce();
    expect(client.loginRedirect).not.toHaveBeenCalled();
  });

  it("keeps initialization retry failures visible and recoverable", async () => {
    const client = fakeClient();
    client.initialize = vi.fn().mockRejectedValue(new Error("initialization failed"));
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    await userEvent.click(await screen.findByRole("button", {name: /retry sign-in/i}));
    expect(await screen.findByRole("alert")).toHaveTextContent(/secure sign-in failed/i);
    expect(client.initialize).toHaveBeenCalledTimes(2);
    expect(client.loginRedirect).not.toHaveBeenCalled();
  });

  it("shows a recoverable error when login redirect fails", async () => {
    const client = fakeClient();
    client.loginRedirect = vi.fn().mockRejectedValue(new Error("redirect failed"));
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    await waitFor(() => expect(screen.getByRole("button", {name: "Sign in"})).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", {name: "Sign in"}));
    expect(await screen.findByRole("alert")).toHaveTextContent(/secure sign-in failed/i);
    expect(client.loginRedirect).toHaveBeenCalledOnce();
  });

  it("deduplicates concurrent interactive redirects after silent acquisition", async () => {
    const client = fakeClient();
    const required = new InteractionRequiredAuthError("interaction_required", "interaction required");
    client.acquireTokenSilent = vi.fn().mockRejectedValue(required);
    let releaseRedirect!: () => void;
    client.acquireTokenRedirect = vi.fn(() => new Promise<void>((resolve) => {
      releaseRedirect = resolve;
    }));
    render(<AuthProvider config={entraConfig} client={client}><Consumer /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("name")).toHaveTextContent("Alex Morgan"));
    const auth = screen.getByRole("button", {name: "Get token"});
    await act(async () => {
      auth.click();
      auth.click();
      await Promise.resolve();
    });
    expect(client.acquireTokenSilent).toHaveBeenCalledTimes(2);
    expect(client.acquireTokenRedirect).toHaveBeenCalledOnce();
    await act(async () => releaseRedirect());
  });
});
