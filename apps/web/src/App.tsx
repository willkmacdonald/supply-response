import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import CaseHeader from './components/CaseHeader';
import EvidencePanel from './components/EvidencePanel';
import ExposurePanel from './components/ExposurePanel';
import NarrativePanel from './components/NarrativePanel';
import ScenarioTable from './components/ScenarioTable';
import ApprovalPanel from './components/ApprovalPanel';
import type { CaseDetail, NarrativeResponse } from './types';

export default function App() {
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [narrativeBusy, setNarrativeBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createCase('RL-001');
      await api.analyze(created.case_id);
      setDetail(await api.getCase(created.case_id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void start();
  }, [start]);

  const loadNarrative = async (caseId: string) => {
    setNarrativeBusy(true);
    try {
      setNarrative(await api.narrative(caseId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setNarrativeBusy(false);
    }
  };

  const decide = async (scenarioId: string, approve: boolean, rationale: string) => {
    if (!detail) return;
    setBusy(true);
    try {
      if (approve) {
        await api.approve(detail.case_id, scenarioId, rationale);
      } else {
        await api.reject(detail.case_id, scenarioId, rationale);
      }
      setDetail(await api.getCase(detail.case_id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="console">
      <h1>Supply Response decision console</h1>
      <p className="subtitle">All data is fictional and prefixed with RL-.</p>

      {error && <p className="error">{error}</p>}
      {!detail && <p>{busy ? 'Loading case…' : 'No case loaded.'}</p>}

      {detail && (
        <>
          <CaseHeader detail={detail} />
          <EvidencePanel detail={detail} />
          <ExposurePanel exposure={detail.exposure} />
          <ScenarioTable scenarios={detail.scenarios} />
          {narrative ? (
            <NarrativePanel narrative={narrative} />
          ) : (
            <section className="panel">
              <button
                disabled={narrativeBusy || detail.status === 'new'}
                onClick={() => void loadNarrative(detail.case_id)}
              >
                {narrativeBusy ? 'Generating narrative…' : 'Generate decision narrative'}
              </button>
            </section>
          )}
          <ApprovalPanel detail={detail} busy={busy} onDecide={decide} />
        </>
      )}
    </main>
  );
}
