# Independent approval browser release

September 13, 2026 (America/Chicago). Source `afbf8db`, revision
`ca-sr-demo--0000029`. Deployed, but real Taylor acceptance is incomplete.

## Delivered and observed

- Five stage tabs and exact authenticated Alex/Taylor workspace routing.
- Independent approval enabled for new cases only. Historical cases retain their
  saved workflow. Spending strictly above $20,000 requires Taylor, followed by
  separate Alex final approval.
- Live Microsoft sign-in as Alex succeeded. A new case was created and analyzed
  through live services; UI source retrieval is dated September 14, 03:22 UTC.
- Alex submitted the combined response for $24,750. The deployed UI shows
  “Waiting for Taylor to review the proposed spending” and an exact review link.
- Taylor's existing account was independently resolved as
  `taybro@willmacdonald.com`, object `f941ed6c-d1d7-482a-b0f6-8b5f5be51e31`.
  Her sign-in is at the Microsoft password screen; no password was retrieved,
  entered, reset or changed by this verification.

## Resume this exact browser journey

- Case: `RL-CASE-bcbb8740-c770-42fd-aa67-981d08b66383`
- Analysis: `RL-ANALYSIS-aa9e5be1-6d28-491e-a179-0eb4752bf00c`
- Review: `RL-FINANCE-e5ef2083-55ae-4605-9756-db242d12149b`
- [Alex case](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/?caseId=RL-CASE-bcbb8740-c770-42fd-aa67-981d08b66383&analysisId=RL-ANALYSIS-aa9e5be1-6d28-491e-a179-0eb4752bf00c)
- [Taylor review](https://ca-sr-demo.orangehill-337f5d48.eastus2.azurecontainerapps.io/?financeReviewId=RL-FINANCE-e5ef2083-55ae-4605-9756-db242d12149b)

Next: complete Taylor sign-in, reject with a reason, observe Alex's rejection,
resubmit, approve as Taylor, then separately finalize as Alex. Do not represent
local fixture proof as this real-account journey. Keep existing browser tabs;
do not create another case merely to resume verification.

## Supporting verification

- Parent regression: 561 backend/API/auth/Finance/execution/persistence/deployment
  tests passed, 11 skipped, fabric_live excluded, one inherited warning.
- 346 frontend tests in 24 files passed; TypeScript/Vite production build passed.
- Local actual React components with explicitly simulated API responses passed
  the complete reject/resubmit/approve/final path at 1440px and 390px, no overflow.
  Screenshots are under `.artifacts/approval-browser/`. Final wording regression
  was observed failing and then passing; final approval no longer says required
  after it has already been recorded.
- Native isolated SQL Server upgrade test passed. Reviewed additive live upgrade
  preserved 12 old cases, 8 analyses, 1 decision and identical payload hashes,
  schema12, trusted constraints and repeat application. No permission changes.
- Azure validation: existing target preflight, official azure.yaml schema,
  provision preview, package, Docker/build arguments, static/live resource roles.
- ACR run `ch1k` succeeded. Image digest
  `sha256:cc7716326e2758eaca834b531b81a679108ea4d4ad384580ff371af031b5661d`.
  Revision29 is Healthy/Running/Provisioned, latest-ready, 100% traffic, scale0–2.
  Live Fabric/Foundry smoke passed. Existing health timeouts were safely retried
  before replacing the previous revision.

## Not delivered by this milestone

Independent approval execution, option-specific action planning, email sending,
inbound email trigger and complete real Taylor approval acceptance. Independent
decisions retain their pending work without launching legacy combined-response
execution. No email, action, simulated playback, new identity or permission was
performed during this release. No Power BI artifact was changed.
