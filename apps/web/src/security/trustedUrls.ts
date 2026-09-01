const fixedHosts = new Set([
  "app.powerbi.com",
  "teams.microsoft.com",
  "outlook.office.com",
  "outlook.office365.com",
]);

const credentialParameter = /(?:^|[?&])(?:access_token|client_secret|assertion|sig|token|code)=/i;

export type CitationClassification = "fabric" | "work_iq" | "untrusted";

export function trustedServerCitation(value: string | null | undefined, classification: CitationClassification | null | undefined, tenantSharePointHost: string | null | undefined): string | null {
  if (!value || !classification || classification === "untrusted") return null;
  try {
    const url = new URL(value);
    let decodedSearch = "";
    try { decodedSearch = decodeURIComponent(url.search); } catch { return null; }
    const workIqHosts = new Set(["teams.microsoft.com", "outlook.office.com", "outlook.office365.com", tenantSharePointHost?.toLowerCase()]);
    const expectedHost = classification === "fabric" ? url.hostname === "app.powerbi.com" : workIqHosts.has(url.hostname);
    if (url.protocol !== "https:" || !expectedHost || url.username || url.password || url.port || credentialParameter.test(decodedSearch)) return null;
    return url.href;
  } catch { return null; }
}

export function trustedMicrosoftUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    const trustedHost = fixedHosts.has(url.hostname);
    if (url.protocol !== "https:" || !trustedHost || url.username || url.password || url.port || credentialParameter.test(url.search)) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}
