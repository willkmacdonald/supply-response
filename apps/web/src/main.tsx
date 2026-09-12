import {broadcastResponseToMainFrame} from "@azure/msal-browser/redirect-bridge";
import {defaultEntraConfig} from "./auth/msal";

function showSafeCallbackFailure(): void {
  const root = document.getElementById("root");
  if (!root) return;
  const message = document.createElement("p");
  message.setAttribute("role", "alert");
  message.textContent = "Sign-in could not be completed. Please return to the application and sign in again.";
  root.replaceChildren(message);
}

async function bootstrap(): Promise<void> {
  const callbackPath = defaultEntraConfig
    ? new URL(defaultEntraConfig.redirectUri).pathname
    : null;
  if (callbackPath && window.location.pathname === callbackPath) {
    try {
      await broadcastResponseToMainFrame();
    } catch {
      showSafeCallbackFailure();
    }
    return;
  }
  const {startApplication} = await import("./application");
  startApplication();
}

void bootstrap();
