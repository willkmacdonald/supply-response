import assert from "node:assert/strict";
import test from "node:test";

import {evaluateArtifactView, trustedCitationUrl} from "./citation-verification-policy.mjs";

const expectedExcerpt =
  "We cannot deliver the full 8,000 units on Scenario Day 2. We can offer 3,000 units by air on September 6 at $7.50 per unit.";

const baseline = {
  status: 200,
  navigationUrls: [
    "https://outlook.office.com/mail/deeplink/read/fixture-alpha",
  ],
  finalUrl: "https://outlook.office.com/mail/deeplink/read/fixture-alpha",
  bodyText: `Supplier Alpha update\n${expectedExcerpt}`,
  expectedExcerpt,
  sourceIdentity: "fixture-source-alpha",
  tenantSharePointHost: "tenant.sharepoint.com",
};

test("accepts the exact rendered fictional artifact", () => {
  assert.deepEqual(evaluateArtifactView(baseline), {
    ok: true,
    reason: "verified_artifact",
    sourceIdentity: "fixture-source-alpha",
  });
});

test("normalizes whitespace and case in the distinctive excerpt", () => {
  const bodyText = expectedExcerpt.toUpperCase().replaceAll(" ", "  \n");
  assert.equal(evaluateArtifactView({...baseline, bodyText}).ok, true);
});

test("rejects a generic successful Teams or Outlook shell", () => {
  for (const bodyText of [
    "Microsoft Teams Loading…",
    "Outlook Mail Calendar People",
    "You need to sign in to continue",
    "This item could not be found",
  ]) {
    assert.equal(evaluateArtifactView({...baseline, bodyText}).ok, false);
  }
});
test("rejects successful content from the wrong artifact", () => {
  assert.equal(
    evaluateArtifactView({...baseline, bodyText: "A different supplier message."}).ok,
    false,
  );
});

test("rejects credential URLs and non-default ports", () => {
  assert.equal(
    trustedCitationUrl("https://alex:secret@outlook.office.com/mail/x", "tenant.sharepoint.com"),
    false,
  );
  assert.equal(
    trustedCitationUrl("https://outlook.office.com:8443/mail/x", "tenant.sharepoint.com"),
    false,
  );
});

test("rejects an off-host main-frame redirect", () => {
  assert.equal(
    evaluateArtifactView({
      ...baseline,
      navigationUrls: [baseline.finalUrl, "https://evil.example/capture"],
    }).ok,
    false,
  );
});

test("rejects a login URL even if the page contains the excerpt", () => {
  assert.equal(
    evaluateArtifactView({
      ...baseline,
      finalUrl: "https://login.microsoftonline.com/common/oauth2/authorize",
      navigationUrls: [
        baseline.finalUrl,
        "https://login.microsoftonline.com/common/oauth2/authorize",
      ],
    }).ok,
    false,
  );
});

test("rejects redirect and HTTP failure statuses", () => {
  for (const status of [301, 399, 400, 404, 500]) {
    assert.equal(evaluateArtifactView({...baseline, status}).ok, false);
  }
});
