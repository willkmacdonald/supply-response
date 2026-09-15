import {expect, test, type Page, type Route} from "@playwright/test";

const at = "2026-09-15T14:00:00Z";
const scenarioTime = "2026-09-01T09:00:00-05:00";

const actor = (persona: "ALEX" | "TAYLOR") => ({
  persona_id: `RL-PERSONA-${persona}`,
  effective_roles: [persona === "ALEX" ? "material_planner" : "finance_approver"],
  identity_source: "entra",
  source_id: `RL-ENTRA-${persona}`,
  tenant_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  object_id: persona === "ALEX" ? "11111111-1111-1111-1111-111111111111" : "22222222-2222-2222-2222-222222222222",
  display_name: persona === "ALEX" ? "Alex" : "Taylor",
  user_principal_name: persona === "ALEX" ? "agent@willmacdonald.com" : "taylor@willmacdonald.com",
});

const option = {
  option_id: "RL-OPTION-COMBINED",
  option_kind: "combined",
  name: "Combine expedite, transfer, and resequencing",
  executable: true,
  active_mitigation: true,
  predicted: {uncovered_part_demand: 2300, otif_loss_percentage: 50, revenue_at_risk: "375000.00",
    margin_at_risk: "125000.00", response_cost: "24750.00", protected_customer_order_ids: []},
  assumptions: ["Remaining supplier recovery date is unconfirmed."],
  evidence_ids: [], evidence_requirements: [], blocking_codes: [],
  prerequisite_roles: ["material_planner", "finance_approver"], source_data_lineage: [],
  approval_burden: 2, execution_risk: 6, requested_side_effects: [],
};

function caseRecord(run: number) {
  return {
    case_id: `RL-CASE-RUN-${run}`, template_id: "RL-001", purpose: "showcase", runtime_mode: "live",
    scenario_effective_time: scenarioTime, scenario_timezone: "America/Chicago", status: "awaiting_decision",
    current_analysis_id: `RL-ANALYSIS-RUN-${run}`, current_decision_id: null, display_status: null,
    recorded_at: at, projection_updated_at: at, presenter_run_id: `RL-RUN-${run}`,
    workflow_version: "independent-finance-v1",
    controls: {new_analysis: false, decide: true, retry_action_planning: false, start_playback: false},
  };
}

function analysisRecord(run: number) {
  const caseId = `RL-CASE-RUN-${run}`;
  const analysisId = `RL-ANALYSIS-RUN-${run}`;
  const validation = {policy_version: "v1", blocking_codes: [], global_blocking_codes: [], item_results: []};
  const ranking = {policy_version: "v1", eligible_option_ids: [option.option_id], infeasible_option_ids: [],
    excluded_baseline_ids: [], stages: [], recommended_option_id: option.option_id, no_feasible_mitigation: false};
  return {
    analysis_id: analysisId, case_id: caseId, runtime_mode: "live", scenario_effective_time: scenarioTime,
    analysis_started_at: at, retrieval_window_ends_at: at, created_at: at, material_hash: `${run}`.repeat(64),
    evidence_items: [], evidence_validation: validation, response_options: [option], approval_satisfactions: [],
    ranking, recommendation: null,
    material: {case_id: caseId, template_id: "RL-001", case_purpose: "showcase", runtime_mode: "live",
      corpus: "demo_corpus", scenario_effective_time: scenarioTime, operational_snapshot_json: "{}",
      required_authority_scope: [], evidence: [], conflicts: [], conflict_resolutions: [],
      evidence_validation: validation, response_options: [{...option, name: undefined}], standing_authorizations: [],
      approval_satisfactions: [], ranking, calculation_version: "v1", evidence_policy_version: "v1",
      approval_policy_version: "v1"},
  };
}

function proposalState(run: number, approved: boolean) {
  const analysis = analysisRecord(run);
  const proposal = {case_id: analysis.case_id, analysis_id: analysis.analysis_id,
    analysis_material_hash: analysis.material_hash, option_id: option.option_id, response_cost: "24750.00"};
  const selection = approved ? {selection_id: `RL-SELECTION-${run}`, proposal,
    workflow_version: "independent-finance-v1", submitted_by: actor("ALEX"), submitted_at: at,
    finance_review_id: `RL-REVIEW-${run}`} : null;
  const review = approved ? {review_id: `RL-REVIEW-${run}`, proposal, submitted_by: actor("ALEX"), submitted_at: at,
    status: "approved", reviewed_by: actor("TAYLOR"), reviewed_at: at, reason: null, superseded_at: null} : null;
  return {token: {generation: approved ? 2 : 1, analysis_id: analysis.analysis_id,
    analysis_material_hash: analysis.material_hash, selection_id: selection?.selection_id ?? null},
  selection, review, review_revision: approved ? 2 : null};
}

function decisionRecord(run: number, complete = true) {
  const analysis = analysisRecord(run);
  const approval = proposalState(run, true);
  return {decision_id: `RL-DECISION-RUN-${run}`, case_id: analysis.case_id, analysis_id: analysis.analysis_id,
    analysis_material_hash: analysis.material_hash, kind: "approved", selected_option_id: option.option_id,
    rejection_reason: null, evidence_ids: [], assumptions: option.assumptions, constraints: [],
    prerequisite_roles: option.prerequisite_roles, approval_satisfactions: [], calculation_version: "v1",
    evidence_policy_version: "v1", approval_policy_version: "v1", ranking_policy_version: "v1",
    runtime_mode: "live", scenario_effective_time: scenarioTime, decided_at: at, projection_updated_at: at,
    action_planning_status: complete ? "complete" : "pending", new_analysis_available: false,
    proposal_approval_evidence: {selection: approval.selection, review: approval.review, review_revision: 2}};
}

function actionRecords(run: number, completed = false) {
  return [
    ["prepare_alpha_recovery_draft", "Prepare a supplier communication for review.", "communication_preparation"],
    ["coordinate_alpha_expedited_partial", "Coordinate the approved partial shipment.", "simulation"],
    ["transfer_dallas_to_chicago", "Coordinate the approved Dallas-to-Chicago transfer.", "simulation"],
    ["resequence_priority_production", "Coordinate the approved production resequencing.", "simulation"],
    ["update_disruption_status", "Record the simulated coordination result.", "simulation"],
  ].map(([kind, purpose, execution_mode], index) => ({
    action_id: `RL-ACTION-${run}-${index + 1}`, case_id: `RL-CASE-RUN-${run}`,
    decision_id: `RL-DECISION-RUN-${run}`, kind, owner_kind: "persona", owner_persona_id: "RL-PERSONA-ALEX",
    status: completed ? "completed" : "planned", created_at: at,
    draft_artifact_id: index === 0 ? `RL-DRAFT-${run}` : null, purpose, expected_result: "Recorded demo result.",
    execution_mode, runtime_mode: "live", scenario_effective_time: scenarioTime, projection_updated_at: at,
  }));
}

function emailRecord(run: number, revision: number, reviewed: boolean, send_status: string, subject?: string, body?: string) {
  return {email_id: `RL-EMAIL-${run}`, decision_id: `RL-DECISION-RUN-${run}`, action_id: `RL-ACTION-${run}-1`,
    revision, subject: subject ?? "RL-001 supplier recovery request",
    body: body ?? "Fictional demo — please confirm current recovery timing.",
    from_address: "agent@willmacdonald.com", to_address: "will@willmacdonald.com",
    reviewed_revision: reviewed ? revision : null, reviewed_at: reviewed ? at : null,
    reviewed_by: reviewed ? actor("ALEX") : null, send_status};
}

async function installMockedPresenterApi(page: Page) {
  let activeRun = 0;
  const analyzed = new Set<number>();
  const financed = new Set<number>();
  const finalized = new Set<number>();
  const played = new Set<number>();
  const emailByRun = new Map<number, ReturnType<typeof emailRecord>>();
  let sendCalls = 0;

  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const fulfill = (json: unknown, status = 200) => route.fulfill({json, status});
    const runMatch = /RL-(?:CASE|DECISION)-RUN-(\d+)/.exec(path);
    const run = runMatch ? Number(runMatch[1]) : activeRun;

    if (path === "/api/runtime") return fulfill({runtime_mode: "live", work_iq: "work_iq",
      operational_store: "fabric_sql", agent_runtime: "foundry", power_bi_available: false,
      capability_health: {}, deployment_contract: {tenant_sharepoint_host: "tenant.sharepoint.com"}});
    if (path === "/api/me") return fulfill({mode: "entra", persona_id: "RL-PERSONA-ALEX",
      display_name: "Alex", independent_finance_enabled: true});
    if (path === "/api/inbox/check" && method === "POST") {
      activeRun += 1;
      return fulfill({presenter_run_id: `RL-RUN-${activeRun}`, checked_at: at, incomplete: false, messages: [{
        message_id: `message-${activeRun}`, subject: `[Supply Response Demo] RL-001 | Run ${activeRun}`,
        sender: "will@willmacdonald.com", received_at: at, excerpt: "Supplier Alpha reported a partial shipment.",
        citation_url: `https://outlook.office.com/mail/deeplink/read/run-${activeRun}`,
        internet_message_id: `<run-${activeRun}@example.com>`, review_fingerprint: `${activeRun}`.repeat(64),
        creation_blocker: null, facts: {original_quantity: 8000, part_id: "RL-MAT-10247", plant_name: "Chicago",
          original_due_date: "2026-09-03", partial_quantity: 3000, partial_due_date: "2026-09-06",
          additional_cost_per_unit: "7.50", remaining_quantity: 5000, recovery_date: null},
      }]});
    }
    if (path === "/api/inbox/cases" && method === "POST") {
      return fulfill({...caseRecord(activeRun), current_analysis_id: null, status: "open",
        controls: {new_analysis: true, decide: false, retry_action_planning: false, start_playback: false}}, 201);
    }
    if (path === `/api/cases/RL-CASE-RUN-${run}/analysis` && method === "POST") {
      analyzed.add(run); return fulfill(analysisRecord(run), 201);
    }
    if (path === `/api/cases/RL-CASE-RUN-${run}` && method === "GET") {
      const base = caseRecord(run);
      return fulfill(finalized.has(run) ? {...base, status: played.has(run) ? "monitoring" : "executing",
        current_decision_id: `RL-DECISION-RUN-${run}`, controls: {...base.controls, decide: false,
          start_playback: !played.has(run)}} : base);
    }
    if (path === `/api/cases/RL-CASE-RUN-${run}/analysis` && method === "GET") return fulfill(analysisRecord(run));
    if (path === `/api/cases/RL-CASE-RUN-${run}/proposal` && method === "GET") return fulfill(proposalState(run, financed.has(run)));
    if (path === `/api/cases/RL-CASE-RUN-${run}/proposals` && method === "POST") {
      financed.add(run); return fulfill({selection: proposalState(run, true).selection,
        review: proposalState(run, true).review, review_revision: 2}, 201);
    }
    if (path === `/api/cases/RL-CASE-RUN-${run}/proposal-decisions` && method === "POST") {
      finalized.add(run); emailByRun.set(run, emailRecord(run, 1, false, "draft"));
      return fulfill(decisionRecord(run, false), 201);
    }
    if (path === `/api/decisions/RL-DECISION-RUN-${run}` && method === "GET") return fulfill(decisionRecord(run));
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/actions` && method === "GET") return fulfill(actionRecords(run, played.has(run)));
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/drafts` && method === "GET") return fulfill([]);
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/supplier-email` && method === "GET") return fulfill(emailByRun.get(run));
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/supplier-email` && method === "PUT") {
      const input = request.postDataJSON();
      const next = emailRecord(run, input.revision + 1, false, "draft", input.subject, input.body);
      emailByRun.set(run, next); return fulfill(next);
    }
    if (path.endsWith("/supplier-email/review") && method === "POST") {
      const current = emailByRun.get(run)!; const next = {...current, reviewed_revision: current.revision,
        reviewed_at: at, reviewed_by: actor("ALEX")}; emailByRun.set(run, next); return fulfill(next);
    }
    if (path.endsWith("/supplier-email/send") && method === "POST") {
      sendCalls += 1; const next = {...emailByRun.get(run)!, send_status: "accepted"};
      emailByRun.set(run, next); return fulfill(next);
    }
    if (path.endsWith("/supplier-email/check-send-status") && method === "POST") {
      const next = {...emailByRun.get(run)!, send_status: "sent-confirmed"};
      emailByRun.set(run, next); return fulfill(next);
    }
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/playback` && method === "POST") {
      return fulfill({playback_id: `RL-PLAYBACK-${run}`, case_id: `RL-CASE-RUN-${run}`,
        decision_id: `RL-DECISION-RUN-${run}`, status: "in_progress", started_at: at, completed_at: null,
        failed_at: null, error_code: null, runtime_mode: "live", scenario_effective_time: scenarioTime}, 201);
    }
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/playback` && method === "GET") {
      if (!played.has(run)) {played.add(run); return fulfill({playback_id: `RL-PLAYBACK-${run}`,
        case_id: `RL-CASE-RUN-${run}`, decision_id: `RL-DECISION-RUN-${run}`, status: "completed",
        started_at: at, completed_at: at, failed_at: null, error_code: null, runtime_mode: "live",
        scenario_effective_time: scenarioTime});}
      return fulfill({playback_id: `RL-PLAYBACK-${run}`, case_id: `RL-CASE-RUN-${run}`,
        decision_id: `RL-DECISION-RUN-${run}`, status: "completed", started_at: at, completed_at: at,
        failed_at: null, error_code: null, runtime_mode: "live", scenario_effective_time: scenarioTime});
    }
    if (path === `/api/decisions/RL-DECISION-RUN-${run}/observations` && method === "GET") {
      return fulfill(played.has(run) ? [{observation_id: `RL-OBS-${run}`, case_id: `RL-CASE-RUN-${run}`,
        decision_id: `RL-DECISION-RUN-${run}`, playback_id: `RL-PLAYBACK-${run}`, action_id: null,
        metric: "uncovered_part_demand", observed_value: "2300", unit: "component units",
        predicted_value: "2300", scenario_effective_time: scenarioTime, scenario_timezone: "America/Chicago",
        recorded_at: at, source_reference: "Simulated: RL-001", kind: "simulated", synthetic: true,
        display_label: "Simulated", runtime_mode: "live"}] : []);
    }
    throw new Error(`Unexpected mocked API request: ${method} ${path}`);
  });

  return {sendCount: () => sendCalls, analyzed};
}

async function openInboundRun(page: Page, expectedRun: number) {
  await page.getByRole("button", {name: "Check email for disruptions"}).click();
  await page.getByText("Review disruption").click();
  await page.getByRole("button", {name: "Analyze this disruption"}).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("caseId"))
    .toBe(`RL-CASE-RUN-${expectedRun}`);
  await expect(page.getByRole("tab", {name: "1. Understand the disruption"})).toBeVisible();
}

test("complete mocked presenter journey and a fresh second run do not leak state", async ({page}) => {
  const api = await installMockedPresenterApi(page);
  await page.goto("/");
  await openInboundRun(page, 1);

  await page.getByRole("tab", {name: "3. Choose a response"}).click();
  await page.getByRole("button", {name: "Select Combined response"}).click();
  await page.getByRole("button", {name: "Continue to review and approve"}).click();
  await page.getByRole("button", {name: "Submit for Finance review"}).click();
  await expect(page.getByText(/Taylor approved the proposed spending/)).toBeVisible();
  await page.getByRole("button", {name: "Give final Alex approval"}).click();
  await expect(page.getByRole("heading", {name: "Alex approved this response"})).toBeVisible();

  await page.getByRole("tab", {name: "5. Execute mitigation plan"}).click();
  await expect(page.getByText("Coordinate expedited partial shipment")).toBeVisible();
  await expect(page.getByText("Transfer stock from Dallas to Chicago")).toBeVisible();
  await expect(page.getByText("Prioritize production for customer needs")).toBeVisible();
  await page.getByRole("button", {name: "Run simulated coordination"}).click();
  await expect(page.getByText("Simulated results")).toBeVisible();

  await page.getByLabel("Subject").fill("RL-001 supplier recovery request — presenter edit");
  await page.getByRole("tab", {name: "3. Choose a response"}).click();
  await page.getByRole("tab", {name: "5. Execute mitigation plan"}).click();
  await expect(page.getByLabel("Subject")).toHaveValue("RL-001 supplier recovery request — presenter edit");
  await page.getByRole("button", {name: "Save changes"}).click();
  await expect(page.getByRole("status")).toContainText("Changes saved");
  await page.getByRole("button", {name: "Review this email"}).click();
  await expect(page.getByRole("button", {name: "Send email"})).toBeEnabled();
  await page.getByRole("button", {name: "Send email"}).click();
  await expect(page.getByRole("status")).toHaveText("Accepted by Microsoft 365");
  expect(api.sendCount()).toBe(1);

  await page.evaluate(async () => {
    await fetch("/api/decisions/RL-DECISION-RUN-1/supplier-email/check-send-status", {method: "POST"});
  });
  await page.reload();
  await page.getByRole("tab", {name: "5. Execute mitigation plan"}).click();
  await expect(page.getByText("Sent", {exact: true})).toBeVisible();
  await expect(page.getByText(/Delivered/i)).toHaveCount(0);
  expect(api.sendCount()).toBe(1);

  await page.goto("/");
  await openInboundRun(page, 2);
  expect(api.analyzed.has(2)).toBe(true);
  await page.getByRole("tab", {name: "4. Review and approve"}).click();
  await expect(page.getByText("Choose a response before submitting it for approval.")).toBeVisible();
  await expect(page.getByText(/Taylor approved/)).toHaveCount(0);
  await page.getByRole("tab", {name: "5. Execute mitigation plan"}).click();
  await expect(page.getByText("Approve a response in Review and approve before starting its mitigation plan.")).toBeVisible();
  await expect(page.getByTestId("execution-action")).toHaveCount(0);
  await expect(page.getByText("Simulated results")).toHaveCount(0);
  await expect(page.getByRole("region", {name: "Review the supplier email"})).toHaveCount(0);
  expect(api.sendCount()).toBe(1);
});
