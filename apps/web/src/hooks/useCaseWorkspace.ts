import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {api} from "../api";
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
import {trustedMicrosoftUrl} from "../security/trustedUrls";

export type WorkspaceOperation =
  | "initializing"
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
  decisionBlocked: boolean;
  create: (purpose?: CasePurpose) => Promise<void>;
  analyze: () => Promise<void>;
  selectOption: (option: ResponseOption) => void;
  approve: () => Promise<void>;
  reject: (reason: string) => Promise<void>;
  retryPlanning: () => Promise<void>;
  retryAction: (actionId: string) => Promise<void>;
  startPlayback: () => Promise<void>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
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
): Promise<T> {
  let current = initial;
  for (let attempt = 0; pending(current) && attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    await delay(POLL_INTERVAL_MS);
    current = await read();
  }
  if (pending(current)) throw new Error(`Timed out waiting for ${description}.`);
  return current;
}

export function useCaseWorkspace(): CaseWorkspaceState {
  const initialized = useRef(false);
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

  const create = useCallback(async (purpose: CasePurpose = "showcase") => {
    setOperation("creating");
    setError(null);
    try {
      const created = await api.createCase(purpose);
      setCaseInstance(created);
      setAnalysis(null);
      setSelectedOption(null);
      setDecision(null);
      setActions([]);
      setDrafts([]);
      setPlayback(null);
      setObservations([]);
    } catch (caught) {
      setError(`Unable to initialize the Case workspace. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, []);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void api.runtime()
      .then(setRuntime)
      .catch((caught) => setError(`Unable to initialize the Case workspace. ${message(caught)}`))
      .finally(() => setOperation(null));
  }, []);

  const analyze = useCallback(async () => {
    if (!caseInstance) return;
    setOperation("analyzing");
    setError(null);
    try {
      const nextAnalysis = await api.analyze(caseInstance.case_id);
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
    } catch (caught) {
      setError(`Analysis failed. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, [caseInstance]);

  const selectOption = useCallback((option: ResponseOption) => {
    if (option.executable) setSelectedOption(option);
  }, []);

  const loadExecution = useCallback(async (decisionId: string) => {
    const [nextActions, nextDrafts] = await Promise.all([
      api.actions(decisionId),
      api.drafts(decisionId),
    ]);
    setActions(nextActions);
    setDrafts(nextDrafts);
  }, []);

  const approve = useCallback(async () => {
    if (!caseInstance || !analysis || !selectedOption) return;
    setOperation("deciding");
    setError(null);
    try {
      const recorded = await api.decide(caseInstance.case_id, {
        analysis_id: analysis.analysis_id,
        kind: "approved",
        selected_option_id: selectedOption.option_id,
      }, `RL-WEB-${caseInstance.case_id}-${analysis.analysis_id}-approved`);
      setDecision(recorded);
      if (recorded.action_planning_status === "pending") setOperation("planning");
      const planned = await pollWhile(
        recorded,
        () => api.decision(recorded.decision_id),
        (current) => current.action_planning_status === "pending",
        "action planning",
      );
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
      if (planned.action_planning_status === "complete") await loadExecution(planned.decision_id);
    } catch (caught) {
      setError(`Decision failed. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, [analysis, caseInstance, loadExecution, selectedOption]);

  const reject = useCallback(async (reason: string) => {
    if (!caseInstance || !analysis || !reason.trim()) return;
    setOperation("deciding");
    setError(null);
    try {
      const recorded = await api.decide(caseInstance.case_id, {
        analysis_id: analysis.analysis_id,
        kind: "rejected",
        rejection_reason: reason.trim(),
      }, `RL-WEB-${caseInstance.case_id}-${analysis.analysis_id}-rejected`);
      setDecision(recorded);
      setCaseInstance((current) => current ? {
        ...current,
        status: "decision_rejected",
        current_decision_id: recorded.decision_id,
        controls: {...current.controls, decide: false, new_analysis: true},
      } : current);
    } catch (caught) {
      setError(`Decision failed. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, [analysis, caseInstance]);

  const retryPlanning = useCallback(async () => {
    if (!decision) return;
    setOperation("planning");
    setError(null);
    try {
      const retried = await api.retryPlanning(decision.decision_id);
      setDecision(retried);
      const planned = await pollWhile(
        retried,
        () => api.decision(retried.decision_id),
        (current) => current.action_planning_status === "pending",
        "action planning",
      );
      setDecision(planned);
      if (planned.action_planning_status === "complete") await loadExecution(planned.decision_id);
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
      setError(`Action planning retry failed. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, [decision, loadExecution]);

  const retryAction = useCallback(async (actionId: string) => {
    if (!decision) return;
    setError(null);
    try {
      const retried = await api.retryAction(decision.decision_id, actionId);
      setActions((current) => current.map((action) =>
        action.action_id === retried.action_id ? retried : action
      ));
    } catch (caught) {
      setError(`Action retry failed. ${message(caught)}`);
    }
  }, [decision]);

  const startPlayback = useCallback(async () => {
    if (!decision) return;
    setOperation("playback");
    setError(null);
    try {
      const started = await api.startPlayback(decision.decision_id);
      setPlayback(started);
      const nextPlayback = await pollWhile(
        started,
        () => api.playback(decision.decision_id),
        (current) => current.status !== "completed" && current.status !== "failed",
        "simulated playback",
      );
      setPlayback(nextPlayback);
      if (nextPlayback.status === "failed") throw new Error("Simulated playback failed on the server.");
      const nextObservations = await api.observations(decision.decision_id);
      setObservations(nextObservations);
    } catch (caught) {
      setError(`Simulated execution failed. ${message(caught)}`);
    } finally {
      setOperation(null);
    }
  }, [decision]);

  const decisionBlocked = useMemo(() => {
    if (!analysis) return true;
    const stale = analysis.evidence_validation.item_results.some((item) => item.freshness === "stale");
    const blocked = analysis.evidence_validation.blocking_codes.length > 0
      || analysis.evidence_validation.global_blocking_codes.length > 0;
    const missingRequiredLiveCitation = analysis.runtime_mode === "live"
      && analysis.evidence_items.some((item) =>
        item.requirement === "required_authoritative"
        && !trustedMicrosoftUrl(item.citation_url)
      );
    const superseded = caseInstance?.current_analysis_id !== null
      && caseInstance?.current_analysis_id !== analysis.analysis_id;
    return stale || blocked || superseded || missingRequiredLiveCitation;
  }, [analysis, caseInstance]);

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
    decisionBlocked,
    create,
    analyze,
    selectOption,
    approve,
    reject,
    retryPlanning,
    retryAction,
    startPlayback,
  };
}
