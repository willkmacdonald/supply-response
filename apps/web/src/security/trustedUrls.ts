const fixedHosts = new Set([
  "app.powerbi.com",
  "teams.microsoft.com",
  "outlook.office.com",
  "outlook.office365.com",
]);

const credentialParameter = /(?:^|[?&])(?:access_token|client_secret|assertion|sig|token|code)=/i;

export function trustedMicrosoftUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    const trustedHost = fixedHosts.has(url.hostname)
      || (url.hostname.endsWith(".sharepoint.com") && url.hostname.split(".").length >= 3);
    if (url.protocol !== "https:" || !trustedHost || url.username || url.password || url.port || credentialParameter.test(url.search)) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}
