const fixedHosts = new Set([
  "app.powerbi.com",
  "teams.microsoft.com",
  "outlook.office.com",
  "outlook.office365.com",
  "outlook.cloud.microsoft",
]);

const outlookHosts = new Set([
  "outlook.office.com",
  "outlook.office365.com",
  "outlook.cloud.microsoft",
]);

const credentialParameter = /(?:^|[?&])(?:access_token|client_secret|assertion|sig|token|code)=/i;

export type CitationClassification = "fabric" | "work_iq" | "untrusted";

export function trustedOutlookUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    let decodedSearch = "";
    try { decodedSearch = decodeURIComponent(url.search); } catch { return null; }
    if (url.protocol !== "https:" || !outlookHosts.has(url.hostname) || url.username || url.password || url.port || credentialParameter.test(decodedSearch)) return null;
    if (url.hostname === "outlook.cloud.microsoft" || url.pathname !== "/owa/") return url.href;

    const allowedParameters = new Set(["ItemID", "exvsurl", "viewmodel", "EntityRepresentationId"]);
    if ([...url.searchParams.keys()].some(key => !allowedParameters.has(key))) return null;
    const itemId = url.searchParams.get("ItemID");
    if (!itemId || itemId.length > 2048 || /\s|[\u0000-\u001f\u007f]/.test(itemId)) return null;
    if (url.searchParams.has("exvsurl") && url.searchParams.get("exvsurl") !== "1") return null;
    if (url.searchParams.has("viewmodel") && url.searchParams.get("viewmodel") !== "ReadMessageItem") return null;

    const pathId = itemId.replaceAll("/", "-").replaceAll("+", "_");
    const current = new URL(`https://outlook.cloud.microsoft/mail/deeplink/read/${encodeURIComponent(pathId)}`);
    current.searchParams.set("ItemID", itemId);
    current.searchParams.set("exvsurl", "1");
    return current.href;
  } catch { return null; }
}

export function trustedServerCitation(value: string | null | undefined, classification: CitationClassification | null | undefined, tenantSharePointHost: string | null | undefined): string | null {
  if (!value || !classification || classification === "untrusted") return null;
  try {
    const url = new URL(value);
    let decodedSearch = "";
    try { decodedSearch = decodeURIComponent(url.search); } catch { return null; }
    const workIqHosts = new Set(["teams.microsoft.com", ...outlookHosts, tenantSharePointHost?.toLowerCase()]);
    const expectedHost = classification === "fabric" ? url.hostname === "app.powerbi.com" : workIqHosts.has(url.hostname);
    if (url.protocol !== "https:" || !expectedHost || url.username || url.password || url.port || credentialParameter.test(decodedSearch)) return null;
    if (outlookHosts.has(url.hostname)) return trustedOutlookUrl(url.href);
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
    if (outlookHosts.has(url.hostname)) return trustedOutlookUrl(url.href);
    return url.href;
  } catch {
    return null;
  }
}
