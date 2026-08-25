import { useState } from 'react';
import type { CaseDetail } from '../types';

interface Props {
  detail: CaseDetail;
  busy: boolean;
  onDecide: (scenarioId: string, approve: boolean, rationale: string) => void;
}

export default function ApprovalPanel({ detail, busy, onDecide }: Props) {
  const executable = detail.scenarios.filter((scenario) => scenario.executable);
  const [scenarioId, setScenarioId] = useState(executable[0]?.scenario_id ?? '');
  const [rationale, setRationale] = useState('');

  return (
    <section className="panel">
      <h3>Approval</h3>
      <label>
        Scenario{' '}
        <select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
          {executable.map((scenario) => (
            <option key={scenario.scenario_id} value={scenario.scenario_id}>
              {scenario.scenario_id} — {scenario.title}
            </option>
          ))}
        </select>
      </label>
      <p>
        <textarea
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
          placeholder="Rationale recorded in the action ledger"
          rows={3}
          cols={70}
        />
      </p>
      <button disabled={busy || !scenarioId} onClick={() => onDecide(scenarioId, true, rationale)}>
        Approve
      </button>
      <button
        className="secondary"
        disabled={busy || !scenarioId}
        onClick={() => onDecide(scenarioId, false, rationale)}
      >
        Reject
      </button>

      {detail.actions.length > 0 && (
        <>
          <h4>Action ledger</h4>
          <ul>
            {detail.actions.map((action) => (
              <li key={action.action_id}>
                {action.action_id} · {action.status} · {action.scenario_id} · {action.decided_by}
                <ul>
                  {action.follow_up_tasks.map((task) => (
                    <li key={task}>{task}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
