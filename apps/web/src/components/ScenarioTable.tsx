import { currency } from '../api';
import type { ScenarioEvaluation } from '../types';

export default function ScenarioTable({ scenarios }: { scenarios: ScenarioEvaluation[] }) {
  return (
    <section className="panel">
      <h3>Ranked response scenarios</h3>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Scenario</th>
            <th>Cost</th>
            <th>Revenue protected</th>
            <th>OTIF lines at risk</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((scenario) => (
            <tr
              key={scenario.scenario_id}
              className={scenario.executable ? (scenario.recommended ? 'recommended' : '') : 'blocked'}
            >
              <td>{scenario.rank}</td>
              <td>
                <strong>{scenario.scenario_id}</strong> {scenario.title}
                <div>{scenario.description}</div>
              </td>
              <td>{currency(scenario.response_cost)}</td>
              <td>{currency(scenario.revenue_protected)}</td>
              <td>{scenario.otif_lines_at_risk}</td>
              <td>
                {scenario.executable
                  ? scenario.recommended
                    ? 'Recommended'
                    : 'Executable'
                  : `Not executable — ${scenario.blocking_constraint ?? 'blocked'}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
