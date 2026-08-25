import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ScenarioTable from './ScenarioTable';
import type { ScenarioEvaluation } from '../types';

const scenario = (overrides: Partial<ScenarioEvaluation>): ScenarioEvaluation => ({
  scenario_id: 'RL-SCN-001',
  disruption_id: 'RL-001',
  scenario_type: 'accept_delay',
  title: 'Accept the delay',
  description: 'Do nothing.',
  calculation_version: '1.0.0',
  evaluated_at: '2025-09-01T12:00:00Z',
  executable: true,
  conditional: false,
  blocking_constraint: null,
  requires_approval: true,
  approver_roles: [],
  response_cost: 0,
  revenue_protected: 0,
  net_benefit: 0,
  revenue_at_risk: 0,
  margin_at_risk: 0,
  otif_lines_at_risk: 0,
  first_stockout_date: null,
  max_shortage_qty: 0,
  score: 0,
  rank: 1,
  recommended: false,
  assumptions: [],
  evidence: [],
  open_questions: [],
  ...overrides
});

describe('ScenarioTable', () => {
  it('marks non-executable scenarios with their blocking constraint', () => {
    render(
      <ScenarioTable
        scenarios={[
          scenario({ scenario_id: 'RL-SCN-006', recommended: true, rank: 1 }),
          scenario({
            scenario_id: 'RL-SCN-005',
            rank: 2,
            executable: false,
            blocking_constraint: 'RL-QUALITY-001: supplier not approved'
          })
        ]}
      />
    );

    expect(screen.getByText('Recommended')).toBeDefined();
    expect(screen.getByText(/RL-QUALITY-001/)).toBeDefined();
  });
});
