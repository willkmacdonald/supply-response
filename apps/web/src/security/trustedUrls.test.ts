import {describe, expect, it} from "vitest";
import {trustedServerCitation} from "./trustedUrls";

describe("server-classified citation trust", () => {
  const tenant = "tenant.sharepoint.com";
  it.each([
    "https://tenant.sharepoint.com/sites/quality/item",
    "https://teams.microsoft.com/l/entity/supplier",
  ])("accepts an exact classified tenant URL: %s", (url) => {
    expect(trustedServerCitation(url, "work_iq", tenant)).toBe(url);
  });

  it.each([
    "https://other.sharepoint.com/sites/quality/item",
    "https://tenant.sharepoint.com.evil.example/item",
    "https://user@tenant.sharepoint.com/item",
    "https://tenant.sharepoint.com:444/item",
    "https://tenant.sharepoint.com/item?%74oken=secret",
    "https://TENANT.sharepoint.com/item?access_token=secret",
  ])("rejects cross-tenant and credential-bearing forms: %s", (url) => {
    expect(trustedServerCitation(url, "work_iq", tenant)).toBeNull();
  });

  it("requires the server classification to match the host family", () => {
    expect(trustedServerCitation("https://app.powerbi.com/x", "work_iq", tenant)).toBeNull();
    expect(trustedServerCitation("https://app.powerbi.com/x", "fabric", tenant)).toBe("https://app.powerbi.com/x");
  });
});
