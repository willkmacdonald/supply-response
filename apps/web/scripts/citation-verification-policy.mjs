const APPROVED_MICROSOFT_365_HOSTS = new Set([
  "teams.microsoft.com",
  "outlook.office.com",
  "outlook.office365.com",
]);

const FAILURE_SHELL_MARKERS = [
  "you need to sign in",
  "sign in to continue",
  "loading microsoft teams",
  "this item could not be found",
  "item not found",
  "you don't have access",
  "you do not have access",
  "access denied",
  "something went wrong",
];

export function normalizeArtifactText(value) {
  return typeof value === "string"
    ? value.normalize("NFKC").toLocaleLowerCase("en-US").replace(/\s+/gu, " ").trim()
    : "";
}

export function trustedCitationUrl(rawUrl, tenantSharePointHost) {
  try {
    const parsed = new URL(rawUrl);
    const tenantHost = String(tenantSharePointHost ?? "").trim().toLowerCase();
    const approved =
      APPROVED_MICROSOFT_365_HOSTS.has(parsed.hostname.toLowerCase()) ||
      (tenantHost.length > 0 && parsed.hostname.toLowerCase() === tenantHost);
    return (
      parsed.protocol === "https:" &&
      parsed.username === "" &&
      parsed.password === "" &&
      parsed.port === "" &&
      approved
    );
  } catch {
    return false;
  }
}

export function evaluateArtifactView({
  status,
  navigationUrls,
  finalUrl,
  bodyText,
  expectedExcerpt,
  sourceIdentity,
  tenantSharePointHost,
}) {
  if (!Number.isInteger(status) || status < 200 || status >= 300) {
    return {ok: false, reason: "status"};
  }
  const source = typeof sourceIdentity === "string" ? sourceIdentity.trim() : "";
  const expected = normalizeArtifactText(expectedExcerpt);
  if (!source || expected.length < 24) {
    return {ok: false, reason: "invalid_expectation"};
  }
  const navigations = Array.isArray(navigationUrls) ? navigationUrls : [];
  if (
    navigations.length === 0 ||
    !navigations.every((url) => trustedCitationUrl(url, tenantSharePointHost)) ||
    !trustedCitationUrl(finalUrl, tenantSharePointHost)
  ) {
    return {ok: false, reason: "unsafe_navigation"};
  }
  const rendered = normalizeArtifactText(bodyText);
  if (FAILURE_SHELL_MARKERS.some((marker) => rendered.includes(marker))) {
    return {ok: false, reason: "login_error_or_loading_shell"};
  }
  if (!rendered.includes(expected)) {
    return {ok: false, reason: "artifact_marker_missing"};
  }
  return {ok: true, reason: "verified_artifact", sourceIdentity: source};
}
