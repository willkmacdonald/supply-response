# Work IQ discovery investigation — controlled live results

Date: 2026-09-08. Read-only operator diagnostic through the existing Work IQ
CLI 1.0.0, explicitly selecting Alex. No production code/configuration changes,
deployment, source edits, permissions changes, or separate Graph client.

## Outcome

The supplier email can be independently located and read. Its actual body
exactly matches the approved corpus, but its discovered ID does not match the
configured supplier source binding. The cause/history of that saved-ID mismatch
has not been established; no replacement binding was accepted or persisted.

Jordan's channel post can be independently located through bounded structured
Work IQ entity queries, individually read, and accepted by the existing evidence
validator. This does not demonstrate successful natural-language Teams discovery.

Neither finding is application-authenticated MCP/OBO acceptance. The website
remains unchanged; no successful normal Analyze flow is claimed.

## What was executed

All raw answers, candidate identifiers, and bodies stayed in the diagnostic
process's memory. Reinspection used those retained responses, not repeated queries.
Only sanitized outcomes are recorded here.

1. One supplier `ask` using the current production topic question; one quality
   `ask` using the original topic-only question requesting individual source
   locations for Jordan's RL-001 Beta post in the named demo Team/General channel.
   Neither supplied expected IDs or copied source facts. The quality comparison
   did not retest the newer explicit complete-channel-link prompt.
2. One mail entity query:
   `/me/messages?$search=%22RL-Supplier%20Alpha%22&$top=5&$select=id,subject,from,receivedDateTime`.
3. Resolve `Supply Response Demo` from `/me/joinedTeams`, then `General` from
   `/teams/{returned-team-id}/channels`. Validate returned locations against the
   configured scope before reading one channel-message page with `$top=10`.
   No pagination was followed.
4. Individually read the sole supplier topic/sender candidate using its returned
   ID. This was an isolated diagnostic body read despite the configured-ID
   mismatch, not a change to the application's fail-closed acceptance gate.
5. Select the sole Jordan/topic-matching channel post from the returned page,
   check its expected ID, and individually read its discovered resource path.
6. Verify `/me?$select=id,userPrincipalName` against Alex's trusted object ID and
   UPN. Both matched. Run the existing `evidence_from_message` validator on the
   individually fetched entities, without modifying its binding or checks.

## Observations

| Check | Supplier email | Jordan channel post |
| --- | --- | --- |
| Natural-language result | OWA message links | Chat-context links, not the target channel/post |
| Structured discovery | One candidate, expected sender | One named Team, one General channel, two posts, no next page |
| Discovered ID versus configured ID | Different | Exact match for selected Jordan post |
| Individual body read | Succeeded | Succeeded |
| Existing evidence validator | Rejected at expected source ID | Passed; 167-character normalized body |

### Email identity and content

The OWA ItemID and configured ID were both 152 characters, but differed in 107
positions after Microsoft's Outlook conversion. Neither the Outlook conversion
nor generic base64url character conversion reconciled the configured binding.
This rules out the tested simple encoding substitutions, not every possible
mail-identity translation or historical explanation.

The independently searched email ID **does** equal the `ask` citation's ItemID
after Outlook conversion. Therefore these two discovery methods converge on the
same candidate. The individual read returned that ID, the expected sender/from,
Alex as recipient, a nonempty body, and a parseable citation matching the fetched
ID. The returned 249-character body exactly equals the committed
`data/demo-corpus/supplier-alpha-message.md` after removing its Markdown heading
and normalizing whitespace. No deletion indicator was present.

The local environment note says the configured ID was previously verified in
Alex's mailbox. That historical assertion alone does not explain the current
mismatch. No configured-ID fetch, ID translation, or trust-binding rewrite was
performed in this investigation.

### Teams discovery and retrieval

The natural-language result's conversation and message IDs both differed from
the configured channel/post; links carried `contextType=chat` and lacked team
and tenant parameters. Adding a missing team parameter would not repair those
different identities.

The structured path resolved the human-readable Team and channel names before
reading their bounded page. The selected post matched Jordan's trusted author
ID and the Beta topic, then matched the configured message ID. Its individual
read passed the existing ID, author, channel, timestamp, source-link, and body
validation. Configured IDs were validation assertions, not lookup inputs.

## Recommended next change and boundary

Reconcile the supplier binding against the independently located, exact-corpus
email. Separately approve replacing answer-link-only discovery with Microsoft's
documented bounded entity-query route, at least for Teams. Preserve all author,
location, body, and citation checks; never silently fall back to configured IDs.

Structured queries demonstrate discovery through Work IQ, but not Copilot
semantic discovery. The original approved design chose `ask` for discovery;
adopting this alternative changes that design. CLI success must still be proven
through the application's own Alex MCP/OBO path before production acceptance.

Documentation and limitations: [contract research](2026-09-08-workiq-discovery-contract.md),
[Microsoft mail guidance](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/references/mail-work-iq.md),
[Microsoft Teams guidance](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/references/teams-work-iq.md).
