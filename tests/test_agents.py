"""Tests for the LLM agent modules (offline / deterministic paths only).

All tests run without network access or Azure credentials.  The LLM paths are
not exercised here; they are covered by integration tests when credentials are
available.
"""

from __future__ import annotations

import os

import pytest

from data.fixtures.demo import (
    DEMO_DISRUPTION_ID,
    QUALITY_CONSTRAINT_ID,
    SUPPLIER_ALPHA_ID,
    SUPPLIER_BETA_ID,
    demo_dataset,
    demo_disruption,
)


class TestSignalAgent:
    def test_deterministic_extraction_captures_facts(self):
        from agents.signal.agent import extract

        disruption = demo_disruption()
        result = extract(disruption)

        assert result.disruption_id == DEMO_DISRUPTION_ID
        assert result.supplier_id == SUPPLIER_ALPHA_ID
        assert result.delayed_qty == 8000
        assert result.original_date == "2025-09-03"
        assert result.partial_qty == 3000
        assert result.partial_date == "2025-09-06"
        assert result.revised_date is None
        assert result.recovery_date_confirmed is False
        assert result.source == "deterministic"

    def test_deterministic_extraction_reports_missing_recovery_date(self):
        from agents.signal.agent import extract

        result = extract(demo_disruption())
        assert any("recovery date" in item.lower() for item in result.missing_information)

    def test_deterministic_extraction_includes_citation(self):
        from agents.signal.agent import extract

        result = extract(demo_disruption())
        assert len(result.citations) >= 1
        assert any("RL-001" in c for c in result.citations)

    def test_to_dict_roundtrips(self):
        from agents.signal.agent import extract

        result = extract(demo_disruption())
        d = result.to_dict()
        assert d["disruption_id"] == DEMO_DISRUPTION_ID
        assert d["delayed_qty"] == 8000
        assert d["source"] == "deterministic"

    def test_no_llm_called_when_endpoint_absent(self, monkeypatch):
        """Passing an email body without AZURE_OPENAI_ENDPOINT uses deterministic."""
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.signal.agent import extract

        result = extract(demo_disruption(), email_body="some email text")
        assert result.source == "deterministic"


class TestContextAgent:
    def test_deterministic_context_returns_quality_constraint(self):
        from agents.context.agent import retrieve

        dataset = demo_dataset()
        disruption = demo_disruption()
        result = retrieve(disruption, dataset)

        assert result.source == "deterministic"
        references = [c["reference"] for c in result.constraints]
        assert QUALITY_CONSTRAINT_ID in references

    def test_deterministic_context_identifies_blocked_supplier(self):
        from agents.context.agent import retrieve

        dataset = demo_dataset()
        disruption = demo_disruption()
        result = retrieve(disruption, dataset)

        beta_constraints = [
            c for c in result.constraints if c["supplier_id"] == SUPPLIER_BETA_ID
        ]
        assert beta_constraints
        assert beta_constraints[0]["status"] == "not_approved"

    def test_policies_always_returned(self):
        from agents.context.agent import retrieve

        result = retrieve(demo_disruption(), demo_dataset())
        assert len(result.policies) >= 1

    def test_to_dict_roundtrips(self):
        from agents.context.agent import retrieve

        result = retrieve(demo_disruption(), demo_dataset())
        d = result.to_dict()
        assert "constraints" in d
        assert "policies" in d
        assert d["source"] == "deterministic"

    def test_work_iq_stub_falls_back_to_deterministic(self, monkeypatch):
        monkeypatch.setenv("WORK_IQ_ENDPOINT", "https://workiq.example.com")
        from agents.context import agent as context_agent
        import importlib
        importlib.reload(context_agent)

        result = context_agent.retrieve(demo_disruption(), demo_dataset())
        assert result.source == "deterministic"

        monkeypatch.delenv("WORK_IQ_ENDPOINT")


class TestDecisionAgent:
    def _evaluations_and_exposure(self):
        from datetime import datetime, timezone
        from data.fixtures.demo import HORIZON_END, HORIZON_START
        from services.scenarios.evaluator import (
            EvaluationContext,
            calculate_baseline,
            evaluate_scenarios,
        )

        dataset = demo_dataset()
        disruption = demo_disruption()
        context = EvaluationContext(
            disruption=disruption,
            horizon_start=HORIZON_START,
            horizon_end=HORIZON_END,
            inventory_positions=dataset.inventory_positions,
            purchase_orders=dataset.purchase_orders,
            production_orders=dataset.production_orders,
            bom_components=dataset.bom_components,
            customer_orders=dataset.customer_orders,
            customers=dataset.customers,
            transport_options=dataset.transport_options,
            quality_qualifications=dataset.quality_qualifications,
        )
        calculated_at = datetime(2025, 9, 1, 12, 0, tzinfo=timezone.utc)
        exposure = calculate_baseline(context, calculated_at)
        evaluations = evaluate_scenarios(dataset.response_scenarios, context, calculated_at)
        return exposure, evaluations

    def test_deterministic_narrative_contains_recommendation(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.decision.agent import narrate
        from apps.api.services import case_facts, case_uncertainties

        dataset = demo_dataset()
        disruption = demo_disruption()
        exposure, evaluations = self._evaluations_and_exposure()
        facts = case_facts(disruption)
        uncertainties = case_uncertainties(disruption, dataset)

        narrative, source = narrate(facts, uncertainties, exposure, evaluations)

        assert source == "deterministic"
        assert "RL-SCN-006" in narrative
        assert "Recommendation" in narrative

    def test_deterministic_narrative_excludes_non_executable_scenario(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.decision.agent import narrate
        from apps.api.services import case_facts, case_uncertainties

        dataset = demo_dataset()
        disruption = demo_disruption()
        exposure, evaluations = self._evaluations_and_exposure()
        facts = case_facts(disruption)
        uncertainties = case_uncertainties(disruption, dataset)

        narrative, _ = narrate(facts, uncertainties, exposure, evaluations)

        assert "not executable" in narrative
        assert QUALITY_CONSTRAINT_ID in narrative

    def test_deterministic_narrative_uses_verbatim_numbers(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.decision.agent import narrate
        from apps.api.services import case_facts, case_uncertainties

        dataset = demo_dataset()
        disruption = demo_disruption()
        exposure, evaluations = self._evaluations_and_exposure()
        facts = case_facts(disruption)
        uncertainties = case_uncertainties(disruption, dataset)

        narrative, _ = narrate(facts, uncertainties, exposure, evaluations)

        # Revenue at risk should appear in the narrative
        assert "1,071,000" in narrative

    def test_no_llm_called_when_endpoint_absent(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        from agents.decision.agent import narrate
        from apps.api.services import case_facts, case_uncertainties

        dataset = demo_dataset()
        disruption = demo_disruption()
        exposure, evaluations = self._evaluations_and_exposure()

        _, source = narrate(
            case_facts(disruption),
            case_uncertainties(disruption, dataset),
            exposure,
            evaluations,
        )
        assert source == "deterministic"
