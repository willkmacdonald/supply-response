// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

const render = vi.fn();
const broadcastResponseToMainFrame = vi.fn();

vi.mock("react-dom/client", () => ({
  default: {createRoot: vi.fn(() => ({render}))},
}));
vi.mock("@azure/msal-browser/redirect-bridge", () => ({broadcastResponseToMainFrame}));
vi.mock("./auth/msal", () => ({
  defaultEntraConfig: {
    tenantId: "11111111-1111-4111-8111-111111111111",
    webClientId: "22222222-2222-4222-8222-222222222222",
    apiScope: "api://33333333-3333-4333-8333-333333333333/access_as_user",
    redirectUri: "http://localhost:5173/auth/callback",
  },
}));

async function importEntry(): Promise<void> {
  await import("./main");
  await vi.waitFor(() => expect(broadcastResponseToMainFrame.mock.settledResults.length + render.mock.calls.length).toBeGreaterThan(0));
}

beforeEach(() => {
  vi.resetModules();
  render.mockReset();
  broadcastResponseToMainFrame.mockReset().mockResolvedValue(undefined);
  document.body.innerHTML = '<div id="root"></div>';
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("application bootstrap", () => {
  it("runs only the MSAL redirect bridge on the exact configured callback path", async () => {
    window.history.replaceState(null, "", "/auth/callback?code=opaque#state=opaque");

    await importEntry();

    expect(broadcastResponseToMainFrame).toHaveBeenCalledOnce();
    expect(render).not.toHaveBeenCalled();
  });

  it("starts the application on a normal path", async () => {
    window.history.replaceState(null, "", "/cases/RL-CASE-1");

    await importEntry();

    expect(render).toHaveBeenCalledOnce();
    expect(broadcastResponseToMainFrame).not.toHaveBeenCalled();
  });

  it("shows safe guidance without raw callback errors when the bridge fails", async () => {
    window.history.replaceState(null, "", "/auth/callback?code=opaque#state=opaque");
    broadcastResponseToMainFrame.mockRejectedValue(new Error("identity secret callback details"));

    await importEntry();

    expect(screenText()).toContain("Sign-in could not be completed");
    expect(screenText()).toContain("return to the application");
    expect(screenText()).not.toContain("identity secret");
    expect(screenText()).not.toContain("opaque");
    expect(render).not.toHaveBeenCalled();
  });
});

function screenText(): string {
  return document.body.textContent ?? "";
}
