import {describe, expect, it} from "vitest";
import {trustedOutlookUrl, trustedServerCitation} from "./trustedUrls";

it("converts a legacy OWA message link to the current Outlook web route", () => {
  const legacy = "https://outlook.office365.com/owa/?ItemID=message%2Bid%2F%3D&exvsurl=1&viewmodel=ReadMessageItem";
  expect(trustedOutlookUrl(legacy)).toBe(
    "https://outlook.cloud.microsoft/mail/deeplink/read/message_id-%3D?ItemID=message%2Bid%2F%3D&exvsurl=1",
  );
});

describe("server-classified citation trust", () => {
  const tenant = "tenant.sharepoint.com";
  it.each([
    "https://tenant.sharepoint.com/sites/quality/item",
    "https://teams.microsoft.com/l/entity/supplier",
    "https://teams.microsoft.com/l/message/19%3Ademo%40thread.tacv2/1788577543694?groupId=11111111-2222-3333-4444-555555555555&tenantId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&createdTime=1788577543694&parentMessageId=1788577543694",
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
