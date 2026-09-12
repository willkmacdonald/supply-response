import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {ApiRequestError, api, safeErrorMessage} from "../api";
import type {
  AnalysisVersion,
  CaseInstance,
  CasePurpose,
  Decision,
  DraftArtifact,
  ExecutionAction,
  OutcomeObservation,
  Playback,
  ResponseOption,
  RuntimeStatus,
} from "../types";
import {trustedServerCitation} from "../security/trustedUrls";

export type WorkspaceOperation =
  | "initializing"
  | "listing"
  | "reopening"
  | "creating"
  | "analyzing"
  | "deciding"
  | "planning"
  | "playback";

export interface CaseWorkspaceState {
  runtime: RuntimeStatus | null;
  caseInstance: CaseInstance | null;
  analysis: AnalysisVersion | null;
  selectedOption: ResponseOption | null;
  decision: Decision | null;
  actions: ExecutionAction[];
  drafts: DraftArtifact[];
  playback: Playback | null;
  observations: OutcomeObservation[];
  operation: WorkspaceOperation | null;
  error: string | null;
  existingCases: CaseInstance[] | null;
  existingCasesError: string | null;
  decisionBlocked: boolean;
  create: (purpose?: CasePurpose) => Promise<void>;
  loadExistingCases: () => Promise<void>;
  reopen: (caseId: string, expectedAnalysisId?: string | null) => Promise<void>;
  analyze: () => Promise<void>;
  selectOption: (option: ResponseOption) => void;
  approve: () => Promise<void>;
  reject: (reason: string) => Promise<void>;
  retryPlanning: () => Promise<void>;
  retryAction: (actionId: string) => Promise<void>;
  startPlayback: () => Promise<void>;
}

const POLL_INTERVAL_MS = 250;
const MAX_POLL_ATTEMPTS = 240;

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function pollWhile<T>(
  initial: T,
  read: () => Promise<T>,
  pending: (value: T) => boolean,
  description: string,
  active: () => boolean,
): Promise<T> {
  let current = initial;
  for (let attempt = 0; pending(current) && attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    await delay(POLL_INTERVAL_MS);
    if (!active()) return current;
    current = await read();
  }
  if (pending(current)) throw new Error(`Timed out waiting for ${description}.`);
  return current;
}

export function useCaseWorkspace(): CaseWorkspaceState {
  const playbackOperation = useRef<Promise<void> | null>(null);
  const restoration = useRef<Promise<void> | null>(null);
  const restorationKey = useRef<string | null>(null);
  const activeOperation = useRef<number | null>(null);
  const restorationVersion = useRef(0);
  const mounted = useRef(true);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [caseInstance, setCaseInstance] = useState<CaseInstance | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisVersion | null>(null);
  const [selectedOption, setSelectedOption] = useState<ResponseOption | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [actions, setActions] = useState<ExecutionAction[]>([]);
  const [drafts, setDrafts] = useState<DraftArtifact[]>([]);
  const [playback, setPlayback] = useState<Playback | null>(null);
  const [observations, setObservations] = useState<OutcomeObservation[]>([]);
  const [operation, setOperation] = useState<WorkspaceOperation | null>("initializing");
  const [error, setError] = useState<string | null>(null);
  const [existingCases, setExistingCases] = useState<CaseInstance[] | null>(null);
  const [existingCasesError, setExistingCasesError] = useState<string | null>(null);

  const begin = useCallback((kind: WorkspaceOperation) => {
    if (!mounted.current || activeOperation.current !== null) {
      if (mounted.current) setError("Please wait for the current operation to finish, then try again.");
      return null;
    }
    const token = ++restorationVersion.current;
    activeOperation.current = token;
    setOperation(kind);
    return token;
  }, []);
  const valid = useCallback((token: number) => mounted.current && activeOperation.current === token, []);
  const finish = useCallback((token: number) => {
    if (valid(token)) { activeOperation.current = null; setOperation(null); }
  }, [valid]);

  const replaceWorkspaceUrl = useCallback((nextCase: CaseInstance, nextAnalysis: AnalysisVersion | null) => {
    const url = new URL(window.location.href);
    url.searchParams.set("caseId", nextCase.case_id);
    if (nextAnalysis) url.searchParams.set("analysisId", nextAnalysis.analysis_id);
    else url.searchParams.delete("analysisId");
    window.history.replaceState(window.history.state, "", url);
  }, []);

  const clearWorkspace = useCallback(() => {
    setCaseInstance(null); setAnalysis(null); setSelectedOption(null); setDecision(null);
    setActions([]); setDrafts([]); setPlayback(null); setObservations([]);
  }, []);

  const loadExistingCases = useCallback(async () => {
    const token = begin("listing");
    if (token === null) return;
    setExistingCasesError(null);
    try { const cases = await api.cases(); if (valid(token)) setExistingCases(cases); }
    catch (caught) { if (valid(token)) { setExistingCases(null); setExistingCasesError(`Unable to find existing cases. ${safeErrorMessage(caught)}`); } }
    finally { finish(token); }
  }, [begin, valid, finish]);

  const reopen = useCallback((caseId: string, expectedAnalysisId?: string | null): Promise<void> => {
    const key = JSON.stringify([caseId, expectedAnalysisId]);
    if (restoration.current && restorationKey.current === key) return restoration.current;
    const version = begin("reopening");
    if (version === null) return Promise.resolve();
    const running = (async () => {
      setOperation("reopening"); setError(null); clearWorkspace();
      try {
        const firstCase = await api.case(caseId);
        if (firstCase.case_id !== caseId) throw new Error("case identity mismatch");
        if (firstCase.current_decision_id && !firstCase.current_analysis_id) throw new Error("decision has no analysis");
        const analysisId = expectedAnalysisId ?? firstCase.current_analysis_id;
        if (expectedAnalysisId && firstCase.current_analysis_id !== expectedAnalysisId) {
          throw new Error("saved analysis is no longer current");
        }
        let nextAnalysis: AnalysisVersion | null = null;
        let nextDecision: Decision | null = null;
        let nextActions: ExecutionAction[] = [];
        let nextDrafts: DraftArtifact[] = [];
        let nextPlayback: Playback | null = null;
        let nextObservations: OutcomeObservation[] = [];
        if (analysisId) {
          nextAnalysis = await api.currentAnalysis(caseId);
          if (nextAnalysis.case_id !== caseId || nextAnalysis.analysis_id !== analysisId) {
            throw new Error("saved analysis is no longer current");
          }
          if (nextAnalysis.material.case_id !== caseId || nextAnalysis.evidence_items.some(item =>
            item.case_id !== caseId || item.retrieved_for_analysis_id !== analysisId)) {
            throw new Error("analysis evidence identity mismatch");
          }
          if (firstCase.current_decision_id) {
            nextDecision = await api.decision(firstCase.current_decision_id);
            if (nextDecision.decision_id !== firstCase.current_decision_id || nextDecision.case_id !== caseId) {
              throw new Error("decision identity mismatch");
            }
            if (nextDecision.analysis_id !== nextAnalysis.analysis_id) {
              // The server retains an earlier decision when a new analysis is saved.
              // Never attach that approval or its execution state to the new analysis.
              if (!(Date.parse(nextDecision.decided_at) < Date.parse(nextAnalysis.analysis_started_at))) {
                throw new Error("decision identity mismatch");
              }
              nextDecision = null;
            } else if (nextDecision.analysis_material_hash !== nextAnalysis.material_hash) {
              throw new Error("decision identity mismatch");
            }
          }
          if (nextDecision) {
            if (nextDecision.kind === "approved" && (!nextDecision.selected_option_id
              || !nextAnalysis.response_options.some(option => option.option_id === nextDecision!.selected_option_id))) {
              throw new Error("selected option identity mismatch");
            }
            [nextActions, nextDrafts, nextPlayback, nextObservations] = await Promise.all([
              api.actions(nextDecision.decision_id), api.drafts(nextDecision.decision_id),
              api.playback(nextDecision.decision_id).catch(caught => {
                if (caught instanceof ApiRequestError && caught.status === 404 && caught.code === "PLAYBACK_NOT_FOUND") return null;
                throw caught;
              }), api.observations(nextDecision.decision_id),
            ]);
            if (nextActions.some(item => item.case_id !== caseId || item.decision_id !== nextDecision!.decision_id)
              || nextDrafts.some(item => item.decision_id !== nextDecision!.decision_id
                || !nextActions.some(action => action.action_id === item.action_id))
              || (nextPlayback && (nextPlayback.case_id !== caseId || nextPlayback.decision_id !== nextDecision.decision_id))
              || nextObservations.some(item => item.case_id !== caseId || item.decision_id !== nextDecision!.decision_id
                || (item.playback_id !== null && item.playback_id !== nextPlayback?.playback_id)
                || (item.action_id !== null && !nextActions.some(action => action.action_id === item.action_id)))) {
              throw new Error("related record identity mismatch");
            }
          }
        }
        const confirmedCase = await api.case(caseId);
        if (confirmedCase.case_id !== caseId || confirmedCase.current_analysis_id !== firstCase.current_analysis_id
          || confirmedCase.current_decision_id !== firstCase.current_decision_id
          || confirmedCase.projection_updated_at !== firstCase.projection_updated_at) throw new Error("case changed during restoration");
        if (!mounted.current || version !== restorationVersion.current) return;
        setCaseInstance(confirmedCase); setAnalysis(nextAnalysis); setDecision(nextDecision);
        setSelectedOption(nextDecision?.selected_option_id
          ? nextAnalysis?.response_options.find(option => option.option_id === nextDecision!.selected_option_id) ?? null
          : nextDecision ? null : nextAnalysis?.recommendation ?? null);
        setActions(nextActions); setDrafts(nextDrafts); setPlayback(nextPlayback); setObservations(nextObservations);
        replaceWorkspaceUrl(confirmedCase, nextAnalysis);
        setExistingCases(null); setExistingCasesError(null);
      } catch (caught) {
        if (!mounted.current || version !== restorationVersion.current) return;
        clearWorkspace();
        const reason = caught instanceof Error && caught.message === "saved analysis is no longer current"
          ? "This saved analysis is no longer current. Choose the case again to open its current analysis."
          : `Unable to reopen this case. ${safeErrorMessage(caught)}`;
        setError(reason);
      } finally { finish(version); }
    })();
    restoration.current = running;
    restorationKey.current = key;
    void running.finally(() => { if (restoration.current === running) restoration.current = null; });
    return running;
  }, [begin, finish, clearWorkspace, replaceWorkspaceUrl]);

  const create = useCallback(async (purpose: CasePurpose = "showcase") => {
    const token = begin("creating");
    if (token === null) return;
    setError(null);
    try {
      const created = await api.createCase(purpose);
      if (!valid(token)) return;
      setCaseInstance(created);
      setAnalysis(null);
      setSelectedOption(null);
      setDecision(null);
      setActions([]);
      setDrafts([]);
      setPlayback(null);
      setObservations([]);
      replaceWorkspaceUrl(created, null);
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Unable to initialize the Case workspace. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, replaceWorkspaceUrl]);

  useEffect(() => {
    mounted.current = true;
    const token = begin("initializing")!;
    void api.runtime()
      .then(async nextRuntime => {
        if (!valid(token)) return;
        setRuntime(nextRuntime);
        const parameters = new URLSearchParams(window.location.search);
        const caseId = parameters.get("caseId");
        const analysisId = parameters.get("analysisId");
        if (analysisId && !caseId) throw new Error("Analysis bookmark is missing its case ID.");
        finish(token);
        if (caseId) await reopen(caseId, analysisId);
      })
      .catch((caught) => { if (valid(token)) setError(`Unable to initialize the Case workspace. ${safeErrorMessage(caught)}`); })
      .finally(() => finish(token));
    return () => {
      mounted.current = false;
      activeOperation.current = null;
      restorationVersion.current += 1;
      restoration.current = null;
      playbackOperation.current = null;
    };
  }, [begin, valid, finish, reopen]);

  const analyze = useCallback(async () => {
    if (!caseInstance?.controls.new_analysis) return;
    const token = begin("analyzing");
    if (token === null) return;
    setError(null);
    try {
      const nextAnalysis = await api.analyze(caseInstance.case_id);
      if (!valid(token)) return;
      setAnalysis(nextAnalysis);
      setSelectedOption(nextAnalysis.recommendation);
      setDecision(null);
      setActions([]);
      setDrafts([]);
      setPlayback(null);
      setObservations([]);
      setCaseInstance((current) => current ? {
        ...current,
        status: "awaiting_decision",
        current_analysis_id: nextAnalysis.analysis_id,
        current_decision_id: null,
        display_status: null,
        controls: {...current.controls, new_analysis: false, decide: true, retry_action_planning: false, start_playback: false},
      } : current);
      if (caseInstance) replaceWorkspaceUrl(caseInstance, nextAnalysis);
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Analysis failed. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, caseInstance, replaceWorkspaceUrl]);

  const selectOption = useCallback((option: ResponseOption) => {
    if (mounted.current && activeOperation.current === null && option.executable) setSelectedOption(option);
  }, []);

  const loadExecution = useCallback(async (decisionId: string, token: number) => {
    const [nextActions, nextDrafts] = await Promise.all([
      api.actions(decisionId),
      api.drafts(decisionId),
    ]);
    if (!valid(token)) return;
    setActions(nextActions);
    setDrafts(nextDrafts);
  }, [valid]);

  const decisionBlocked = useMemo(() => {
    if (!analysis) return true;
    const stale = analysis.evidence_validation.item_results.some((item) => item.freshness === "stale");
    const blocked = analysis.evidence_validation.blocking_codes.length > 0
      || analysis.evidence_validation.global_blocking_codes.length > 0;
    const missingRequiredLiveCitation = analysis.runtime_mode === "live"
      && analysis.evidence_items.some((item) =>
        item.requirement === "required_authoritative"
        && !trustedServerCitation(item.navigable_citation_url, item.citation_classification, runtime?.deployment_contract?.tenant_sharepoint_host)
      );
    const superseded = caseInstance?.current_analysis_id !== null
      && caseInstance?.current_analysis_id !== analysis.analysis_id;
    return stale || blocked || superseded || missingRequiredLiveCitation;
  }, [analysis, caseInstance, runtime]);

  const approve = useCallback(async () => {
    if (!caseInstance?.controls.decide || !analysis || !selectedOption || decision || decisionBlocked) return;
    const token = begin("deciding");
    if (token === null) return;
    setError(null);
    try {
      const recorded = await api.decide(caseInstance.case_id, {
        analysis_id: analysis.analysis_id,
        kind: "approved",
        selected_option_id: selectedOption.option_id,
      }, `RL-WEB-${caseInstance.case_id}-${analysis.analysis_id}-approved`);
      if (!valid(token)) return;
      setDecision(recorded);
      if (recorded.action_planning_status === "pending") setOperation("planning");
      const planned = await pollWhile(
        recorded,
        () => api.decision(recorded.decision_id),
        (current) => current.action_planning_status === "pending",
        "action planning",
        () => valid(token),
      );
      if (!valid(token)) return;
      setDecision(planned);
      setCaseInstance((current) => current ? {
        ...current,
        current_decision_id: planned.decision_id,
        status: planned.action_planning_status === "complete" ? "executing" : "action_planning",
        display_status: planned.action_planning_status === "failed" ? "Approved — action planning failed" : null,
        controls: {
          ...current.controls,
          decide: false,
          retry_action_planning: planned.action_planning_status === "failed",
          start_playback: planned.action_planning_status === "complete",
        },
      } : current);
      if (planned.action_planning_status === "complete") await loadExecution(planned.decision_id, token);
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Decision failed. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, analysis, caseInstance, loadExecution, selectedOption, decision, decisionBlocked]);

  const reject = useCallback(async (reason: string) => {
    if (!caseInstance?.controls.decide || !analysis || !reason.trim() || decision || decisionBlocked) return;
    const token = begin("deciding");
    if (token === null) return;
    setError(null);
    try {
      const recorded = await api.decide(caseInstance.case_id, {
        analysis_id: analysis.analysis_id,
        kind: "rejected",
        rejection_reason: reason.trim(),
      }, `RL-WEB-${caseInstance.case_id}-${analysis.analysis_id}-rejected`);
      if (!valid(token)) return;
      setDecision(recorded);
      setCaseInstance((current) => current ? {
        ...current,
        status: "decision_rejected",
        current_decision_id: recorded.decision_id,
        controls: {...current.controls, decide: false, new_analysis: true},
      } : current);
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Decision failed. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, analysis, caseInstance, decision, decisionBlocked]);

  const retryPlanning = useCallback(async () => {
    if (!decision || !caseInstance?.controls.retry_action_planning) return;
    const token = begin("planning");
    if (token === null) return;
    setError(null);
    try {
      const retried = await api.retryPlanning(decision.decision_id);
      if (!valid(token)) return;
      setDecision(retried);
      const planned = await pollWhile(
        retried,
        () => api.decision(retried.decision_id),
        (current) => current.action_planning_status === "pending",
        "action planning",
        () => valid(token),
      );
      if (!valid(token)) return;
      setDecision(planned);
      if (planned.action_planning_status === "complete") await loadExecution(planned.decision_id, token);
      if (!valid(token)) return;
      setCaseInstance((current) => current ? {
        ...current,
        status: planned.action_planning_status === "complete" ? "executing" : "action_planning",
        display_status: planned.action_planning_status === "failed" ? "Approved — action planning failed" : null,
        controls: {
          ...current.controls,
          retry_action_planning: planned.action_planning_status === "failed",
          start_playback: planned.action_planning_status === "complete",
        },
      } : current);
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Action planning retry failed. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, decision, caseInstance, loadExecution]);

  const retryAction = useCallback(async (actionId: string) => {
    if (!decision || decision.kind !== "approved" || !actions.some(action => action.action_id === actionId && action.status === "failed")) return;
    const token = begin("planning");
    if (token === null) return;
    setError(null);
    try {
      const retried = await api.retryAction(decision.decision_id, actionId);
      if (!valid(token)) return;
      setActions((current) => current.map((action) =>
        action.action_id === retried.action_id ? retried : action
      ));
    } catch (caught) {
      if (!valid(token)) return;
      setError(`Action retry failed. ${safeErrorMessage(caught)}`);
    } finally {
      finish(token);
    }
  }, [begin, valid, finish, decision, actions]);

  const startPlayback = useCallback((): Promise<void> => {
    if (playbackOperation.current) return playbackOperation.current;
    if (!decision || decision.kind !== "approved" || !caseInstance?.controls.start_playback || playback || actions.length !== 5) return Promise.resolve();
    const token = begin("playback");
    if (token === null) return Promise.resolve();
    const running = (async () => {
      setOperation("playback");
      setError(null);
      try {
        const started = await api.startPlayback(decision.decision_id);
        if (!valid(token)) return;
        setPlayback(started);
        const nextPlayback = await pollWhile(
          started,
          () => api.playback(decision.decision_id),
          (current) => current.status !== "completed" && current.status !== "failed",
          "simulated playback",
          () => valid(token),
        );
        if (!valid(token)) return;
        setPlayback(nextPlayback);
        if (nextPlayback.status === "failed") throw new Error("Simulated playback failed on the server.");
        const nextObservations = await api.observations(decision.decision_id);
        if (!valid(token)) return;
        setObservations(nextObservations);
      } catch (caught) {
        if (!valid(token)) return;
        setError(`Simulated execution failed. ${safeErrorMessage(caught)}`);
      } finally {
        finish(token);
      }
    })();
    playbackOperation.current = running;
    void running.finally(() => {
      if (playbackOperation.current === running) playbackOperation.current = null;
    });
    return running;
  }, [begin, valid, finish, decision, caseInstance, playback, actions.length]);


  return {
    runtime,
    caseInstance,
    analysis,
    selectedOption,
    decision,
    actions,
    drafts,
    playback,
    observations,
    operation,
    error,
    existingCases,
    existingCasesError,
    decisionBlocked,
    create,
    loadExistingCases,
    reopen,
    analyze,
    selectOption,
    approve,
    reject,
    retryPlanning,
    retryAction,
    startPlayback,
  };
}
