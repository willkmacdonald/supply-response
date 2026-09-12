# Traditional and assisted planning walkthrough

Use one existing analyzed fictional case for both routes. Keep the demo tab open,
note the case ID and analysis ID in **Analysis source details** and the visible
**Analysis saved at** time, and use that same case and analysis throughout. This
walkthrough replays those saved records;
it is not evidence of a fresh discovery or retrieval run.

## Reopen the saved case

1. Choose **Find existing cases**. The picker loads only when requested and shows
   each case's planning state, recorded time, and exact case ID.
2. Choose **Reopen** for the recorded case ID. Wait for the saved workspace to
   finish loading, then confirm the case ID and analysis ID match the walkthrough.
3. Refreshing a URL that contains those IDs restores that exact current context.
   If its saved analysis has since been replaced, restoration stops visibly;
   choose the case again only when you intend to open its newer current analysis.

If the case retains a decision from before the current analysis began, the newer
analysis opens with an explicit notice. The earlier approval and actions are not
attached to it. Case and decision identity still must match, and a decision dated
after the current analysis began cannot be treated as an earlier decision.

Reopening is read-only. It reads the stored case, analysis, decision, action,
draft, playback, and observation records that exist; it does not retrieve evidence
again, change retrieval timestamps, create a case, analyze, approve, retry, or run
the simulation. A case may have no analysis yet, and a recorded decision may have
no playback. A failure while loading related records leaves no partially actionable
workspace. This flow restores only the current analysis because there is no
historical-analysis endpoint.

## Explore in Power BI

1. **Investigate the delay.** Open the original supplier email from the disruption
   card. Identify the component, Chicago plant, original quantity and due date,
   then choose **Explore in Power BI**. Confirm the report's case ID and analysis
   ID exactly match the demo and that it says **Snapshot used for this analysis**.
2. **Check available stock.** Review on-hand units, quality holds, protected
   allocation, and usable component units. Then inspect the affected order lines
   and due dates. Treat the saved baseline as the prediction without a response.
3. **Investigate responses.** Review **RL-Supplier Alpha — Current supplier** and
   its proposed shipment, the Dallas plant to Chicago plant transfer, and
   **RL-Supplier Beta — Alternate supplier** and its qualification status.
   Compare quantities, dates, costs, and blockers with the original supplier email
   and Quality Teams post. A qualification review date is not approval or a
   delivery promise.
4. **Weigh the trade-offs.** Compare every saved option using the same units and
   assumptions: response cost, service exposure, parts still needed, and planning
   requirements. No option is highlighted as the recommendation. The planner
   states a proposed response and unresolved questions.
5. **Review the decision.** Open **Actions and outcomes** and describe only the
   recorded decision, action, and outcome states. Keep predictions separate from
   observations and retain the **Simulated** label on simulated observations.

## Review with AI assistance

Return to the existing demo tab without changing its case or analysis. Choose
**Review with AI assistance** and read the three investigation rows in order:
disruption, stock and exposure; response evidence; then option comparison,
recommendation, and review and approval. Show the recommendation and explanation
beside the same saved comparison and original sources. Human judgment still owns
uncertainty, trade-offs, and authorization.

## Presenter notes

- The Power BI route and assisted route use the same fictional case, immutable
  analysis snapshot, permissions, assumptions, units, and option predictions.
- The report's option predictions come from the application's shared saved
  calculation engine. Power BI presents those values; it does not independently
  recalculate the analysis. Do not attribute deterministic arithmetic or ranking
  to Work IQ or an LLM.
- The traditional route is a neutral planning experience using focused report
  pages plus the original email and Teams sources. The assisted route brings the
  same evidence together. The comparison concerns how information is found,
  connected, checked, and interpreted—not whether Power BI can integrate sources.
- Check the exact case, analysis, source-record or option identity, quantity,
  date, status, and units at each destination. A report view of saved evidence is
  presentation, not independent corroboration. Keep unknowns and source links
  visible.
- If a selection is unavailable, a record is missing or ambiguous, the report has
  not caught up, or an ID differs, stop and use the inline source view. Never pick
  a similar record or latest analysis merely to populate the report.
- If the governing decision belongs to a different saved analysis, explain that
  lineage. **No outcomes recorded** means exactly that; it is not a zero result.
- Do not create or analyze a case for rehearsal. Do not approve a response, plan
  execution, start a simulation, or start playback. Re-establish lost demo context
  with **Reopen existing case**; it does not silently create a new case.
- Do not claim measured time, click, accuracy, or operational improvements. Any
  future timing must distinguish cached or replayed material from a fresh run.
