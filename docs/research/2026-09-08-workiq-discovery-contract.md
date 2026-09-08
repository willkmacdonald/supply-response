# Work IQ discovery and source-content contract

Research date: 2026-09-08. Scope: primary Microsoft documentation and Microsoft-owned repositories; no tenant requests or application changes. This is a research proposal, not a verified live result.

## Finding

Microsoft documents structured message discovery through Work IQ entity tools. It does **not** document a guarantee that a natural-language `ask` response supplies canonical, fetchable identifiers for a particular email and Teams channel post. The supported distinction is semantic discovery/synthesis with Copilot versus literal resource querying through Work IQ. Both use Work IQ, but they establish different demonstration claims. [Work IQ overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/overview), [Microsoft Work IQ preview guidance](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/SKILL.md).

The existing approved design specifically requires `ask`-discovered complete locations and forbids filling gaps with configured identifiers or broad enumeration. Replacing that step with structured collection queries would revise that design, even while preserving the Work IQ integration boundary. This note does not make that revision. [Approved local design](../superpowers/specs/2026-09-07-workiq-discovery-evidence-design.md).

## What the public contracts actually promise

| Surface | Documented result | Consequence |
| --- | --- | --- |
| `ask` | Learn describes a JSON string containing `response` and `conversationId`. | No documented typed citation array, canonical mail ID, team/channel/message tuple, or requested JSON-output guarantee. |
| `fetch` | `entityUrls` accepts relative resource paths; each result supplies Graph JSON `data` and `statusCode`. | A collection can discover identifiers; an individual read can retrieve source content. |
| `search_paths` | Matching API path templates and supported operations. | Searches API metadata, not email or Teams messages. |
| `get_schema` | Schema for an API path/operation; current schemas are Graph v1.0. | Describes fields and operations; does not discover message instances. |

Source: [Work IQ MCP tool reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference).

Microsoft's `iq-series` lab instead describes `ask` text plus structured `answer`/`conversationId`. It says `fetch` can use paths discovered from answers, but its actual exercise demonstrates identity questions and a mailbox collection query, not a topic-only discovery followed by canonical retrieval of both an email and a channel post. This is evidence of documentation/envelope variation, not evidence of a guaranteed locator contract. No end-to-end canonical-locator example for this exact requirement was found in the reviewed Learn pages, Work IQ preview references, or this lab; that is a scoped negative finding, not a claim that no such example exists anywhere. [Microsoft IQ Series lab 03](https://github.com/microsoft/iq-series/blob/main/Work-IQ/3-Work-IQ-Tooling-with-MCP-and-Copilot-CLI/cookbook/work-iq-lab03.md).

## Documented alternative: discover entities, then read their bodies

The following path patterns are illustrative, not executable requests with real identifiers. Every identifier must come from the preceding authenticated Work IQ result; none comes from the configured expected-source binding.

### Email

1. Call Work IQ `fetch` on `/me/messages` with a bounded `$search` for independently supplied topic/subject terms and a narrow `$select` including `id,subject,from,receivedDateTime`.
2. Use the returned candidate's `id` to construct `/me/messages/{returned-id}` for an individual Work IQ `fetch`.

Microsoft's mail reference explicitly recommends entity tools for finding individual messages, supplies a quoted/URL-encoded `$search` example, and documents the individual-message path. Exact-subject equality can miss subject prefixes or suffixes; do not assume a natural-language phrase is an exact subject. [Microsoft Work IQ mail reference](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/references/mail-work-iq.md).

Graph's underlying mail search supports property terms such as `subject:`, `from:`, and `received:`. Choose only independently known discovery criteria and encode them correctly. These are structured search predicates, not Copilot semantic retrieval. [Graph mail search parameters](https://learn.microsoft.com/en-us/graph/search-query-parameter).

For the individual read, request the actual `body`, source identity, author, timestamp and `webLink` needed by validation. A preview or Copilot summary is not the full message. Graph documents body retrieval and optional text formatting via a request header; do not assume the Work IQ wrapper exposes that header. Preserve the application's inert HTML-to-text handling when the response body is HTML. [Graph get message](https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0).

### Teams channel post

Resolve the human-readable location using Work IQ `fetch`: `/me/joinedTeams`, then `/teams/{returned-team-id}/channels`. Match the requested team/channel before reading `/teams/{returned-team-id}/channels/{returned-channel-id}/messages`. Microsoft explicitly distinguishes channel posts from chats and warns that their identifiers are not interchangeable. This route discovers location IDs as well as message IDs, but its collection reads must stay bounded. [Microsoft Work IQ Teams reference](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/references/teams-work-iq.md).

The channel-list API supports `$top` and `$expand` only: **do not add mail-style `$search`, `$filter`, or an assumed `$select`**. It returns root posts without replies unless replies are expanded/read separately. Results are ordered by the last modification of the whole reply chain. Therefore this route can locate a matching post in the permitted page, but cannot guarantee discovery of an arbitrary older post. [Graph list channel messages](https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0).

Read a selected root post through Work IQ at `/teams/{returned-team-id}/channels/{returned-channel-id}/messages/{returned-message-id}`. A reply requires `/messages/{returned-parent-id}/replies/{returned-reply-id}`. Preserve the returned `body`, `from`, timestamp, `webUrl`, and complete channel identity for deterministic validation. A chat citation missing the team does not establish either channel resource shape. [Graph get chatMessage](https://learn.microsoft.com/en-us/graph/api/chatmessage-get?view=graph-rest-1.0).

## Limits and unresolved details

- Work IQ documents a default collection `$top` of 25, maximum 100, chat-message cap of 10, and rejection of `$skip`/`$skiptoken`. Its own example contains a next link using `$skip`; that does not override the stated prohibition. Do not assume pagination is usable, or that the generic cap overrides stricter workload limits. Whether the chat-message cap also covers channel posts needs runtime confirmation. [Work IQ tool reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference).
- Tenant policy evaluates paths, operations and request content in addition to authentication, OAuth consent and the user's existing access. A listed path/schema is not proof that a read will be allowed. Mutations are blocked by default; policy denials are governance outcomes and should not trigger alternate-path retries. [Work IQ policy governance](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/policy-governance-mcp).
- The permissions reference documents delegated `WorkIQAgent.Ask`, with admin consent, under `api://workiq.svc.cloud.microsoft`. The overview's mention of four broad permissions is not an enumerated consent recipe. Do not invent additional Work IQ scopes or infer that the application's successful `ask` proves every entity path is authorized. [Work IQ permissions](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/permissions), [overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/overview).
- The overview sketches `call_function /search/query` for semantic search, but the tool reference exposes no search request body, while Graph's search API is `POST /search/query` with a `requests` body. The reviewed material does not provide a consistent callable Work IQ request for searching `chatMessage` entities and retrieving complete channel locators. Treat this as a capability to investigate through actual tool/schema metadata, not an implementation-ready solution. [Work IQ overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/overview), [Graph search query](https://learn.microsoft.com/en-us/graph/api/search-query?view=graph-rest-1.0).
- Mail `ewsId` and Graph `restId` are distinct documented formats. Graph offers explicit ID translation; character substitution alone does not establish that an OWA citation equals the expected Graph entity. Whether translation is exposed and permitted through Work IQ is unverified; this note proposes no direct Graph fallback. [Graph translateExchangeIds](https://learn.microsoft.com/en-us/graph/api/user-translateexchangeids?view=graph-rest-1.0).

## Minimal verification recommendation

First decide the demonstration claim. If success specifically means **Copilot semantic discovery produces complete locators**, the missing locator guarantee remains unresolved; requesting a better answer shape alone is not a documented fix. A typed, supported search-result contract or a successful bounded proof under the application identity is still needed.

If **independent discovery through Work IQ** is sufficient, the smallest concrete experiment is the structured route above, with one narrow mail search and one bounded channel-message page after resolving the named team/channel. Use returned identifiers only; keep the expected IDs exclusively as validation checks. Stop on ambiguity, policy denial, missing target or incomplete pages. Do not compensate by increasing traversal or relaxing the source binding.

Run any future acceptance through the application's actual `https://workiq.svc.cloud.microsoft/mcp` endpoint and Alex OBO identity. The hosted endpoint is documented in Microsoft's preview configuration. The investigation's supplied CLI 1.0.0 `ask` observation uses A2A and is not evidence of the application's MCP/OBO behavior. Public CLI branding alone does not establish transport equivalence. [Microsoft preview configuration](https://github.com/microsoft/work-iq/blob/main/plugins/workiq-preview/skills/workiq-preview/SKILL.md), [Microsoft CLI README](https://github.com/microsoft/work-iq).

Success must include both independently discovered source identities, successful individual Work IQ reads, nonempty actual bodies, and all existing author/location/source/evidence checks passing. Record only bounded diagnostic outcomes; do not persist raw answers, bodies or credentials. No live verification was performed for this note, and no successful evidence pair is claimed.
