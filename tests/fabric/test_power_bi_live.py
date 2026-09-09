from __future__ import annotations

import os
import time
from uuid import uuid4

import pytest

LIVE_SETTINGS = (
    "SUPPLY_RESPONSE_API_BASE_URL",
    "SUPPLY_RESPONSE_ALLOWED_TENANT_ID",
    "SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID",
    "SUPPLY_RESPONSE_POWER_BI_SEMANTIC_MODEL_ID",
)
configured = {name: os.environ.get(name, "").strip() for name in LIVE_SETTINGS}
present = {name for name, value in configured.items() if value}

if not present:
    pytestmark = [
        pytest.mark.fabric_live,
        pytest.mark.power_bi_live,
        pytest.mark.skip(reason="Power BI live settings are not configured"),
    ]
elif present != set(LIVE_SETTINGS):
    missing = sorted(set(LIVE_SETTINGS) - present)
    raise pytest.UsageError(
        "Power BI live settings must be configured together before any "
        "authentication or network access; missing: " + ", ".join(missing)
    )
else:
    pytestmark = [pytest.mark.fabric_live, pytest.mark.power_bi_live]


def _require_success(response):
    response.raise_for_status()
    return response.json()


def _normalized_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    results = payload["results"]
    assert isinstance(results, list) and len(results) == 1
    tables = results[0]["tables"]
    assert isinstance(tables, list) and len(tables) == 1
    rows = tables[0]["rows"]
    assert isinstance(rows, list)
    return [{key.strip("[]"): value for key, value in row.items()} for row in rows]


def _normalized_row(payload: dict[str, object]) -> dict[str, object]:
    rows = _normalized_rows(payload)
    assert len(rows) == 1
    return rows[0]


def _dax_literal(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def test_selected_case_decision_reaches_power_bi_within_sixty_seconds() -> None:
    import httpx
    from azure.identity import AzureCliCredential

    with httpx.Client(
        base_url=configured["SUPPLY_RESPONSE_API_BASE_URL"], timeout=15
    ) as api:
        case = _require_success(
            api.post(
                "/api/cases",
                json={"template_id": "RL-001", "purpose": "showcase"},
            )
        )
        analysis = _require_success(api.post(f"/api/cases/{case['case_id']}/analysis"))
        selected_option_id = analysis["ranking"]["recommended_option_id"]
        decision = _require_success(
            api.post(
                f"/api/cases/{case['case_id']}/decisions",
                headers={"Idempotency-Key": f"power-bi-live-{uuid4()}"},
                json={
                    "analysis_id": analysis["analysis_id"],
                    "kind": "approved",
                    "selected_option_id": selected_option_id,
                },
            )
        )
        actions = _require_success(
            api.get(f"/api/decisions/{decision['decision_id']}/actions")
        )
        assert len(actions) == 5
        _require_success(api.post(f"/api/decisions/{decision['decision_id']}/playback"))

        playback_deadline = time.monotonic() + 60
        observations: list[dict[str, object]] = []
        while time.monotonic() < playback_deadline:
            observations = _require_success(
                api.get(f"/api/decisions/{decision['decision_id']}/observations")
            )
            if len(observations) == 10:
                break
            time.sleep(2)
        assert len(observations) == 10
        assert {item["display_label"] for item in observations} == {"Simulated"}

    credential = AzureCliCredential(
        tenant_id=configured["SUPPLY_RESPONSE_ALLOWED_TENANT_ID"]
    )
    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default")
    query_url = (
        "https://api.powerbi.com/v1.0/myorg/groups/"
        f"{configured['SUPPLY_RESPONSE_FABRIC_WORKSPACE_ID']}/datasets/"
        f"{configured['SUPPLY_RESPONSE_POWER_BI_SEMANTIC_MODEL_ID']}/executeQueries"
    )
    selected_case = _dax_literal(case["case_id"])
    selected_decision = _dax_literal(decision["decision_id"])
    dax = f"""EVALUATE
CALCULATETABLE(
  ROW(
    "case_id", SELECTEDVALUE(CaseCommandCenter[case_id]),
    "decision_id", SELECTEDVALUE(ActionOutcomes[decision_id]),
    "current_decision_id", CaseCommandCenter[Current Decision ID],
    "selected_option_id", SELECTEDVALUE(ActionOutcomes[selected_option_id]),
    "action_count", CaseCommandCenter[Current Actions Count],
    "action_completion", DIVIDE(
        CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "action", ActionOutcomes[action_status] = "completed"),
        CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "action")),
    "simulated_observation_count", CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[record_type] = "observation", ActionOutcomes[observation_kind] = "simulated"),
    "observation_kind", CaseCommandCenter[Current Observation Kind],
    "scenario_effective_time", MAX(ActionOutcomes[scenario_effective_time]),
    "projection_refresh_time", CaseCommandCenter[Projection Refresh Time]
  ),
  TREATAS({{{selected_case}}}, CaseCommandCenter[case_id]),
  TREATAS({{{selected_case}}}, ActionOutcomes[case_id]),
  TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])
)"""
    variance_dax = f"""EVALUATE
CALCULATETABLE(
  UNION(
    ROW("metric", "response_cost", "relative_variance", CALCULATE(
      ActionOutcomes[Observed Variance],
      ActionOutcomes[record_type] = "observation",
      ActionOutcomes[observation_kind] = "simulated",
      ActionOutcomes[metric] = "response_cost")),
    ROW("metric", "remaining_alpha_recovery_date", "relative_variance", CALCULATE(
      ActionOutcomes[Observed Variance],
      ActionOutcomes[record_type] = "observation",
      ActionOutcomes[observation_kind] = "simulated",
      ActionOutcomes[metric] = "remaining_alpha_recovery_date"))
  ),
  TREATAS({{{selected_case}}}, CaseCommandCenter[case_id]),
  TREATAS({{{selected_case}}}, ActionOutcomes[case_id]),
  TREATAS({{{selected_decision}}}, ActionOutcomes[decision_id])
)"""

    deadline = time.monotonic() + 60
    last_row: dict[str, object] = {}
    with httpx.Client(timeout=15) as power_bi:
        while time.monotonic() < deadline:
            payload = _require_success(
                power_bi.post(
                    query_url,
                    headers={"Authorization": f"Bearer {token.token}"},
                    json={
                        "queries": [{"query": dax}],
                        "serializerSettings": {"includeNulls": True},
                    },
                )
            )
            last_row = _normalized_row(payload)
            if (
                last_row.get("case_id") == case["case_id"]
                and last_row.get("decision_id") == decision["decision_id"]
                and last_row.get("action_count") == 5
                and last_row.get("simulated_observation_count") == 10
                and last_row.get("projection_refresh_time") is not None
            ):
                break
            time.sleep(5)

        variance_payload = _require_success(
            power_bi.post(
                query_url,
                headers={"Authorization": f"Bearer {token.token}"},
                json={
                    "queries": [{"query": variance_dax}],
                    "serializerSettings": {"includeNulls": True},
                },
            )
        )
        variance_rows = {
            str(row["metric"]): row.get("relative_variance")
            for row in _normalized_rows(variance_payload)
        }

    assert last_row["case_id"] == case["case_id"]
    assert last_row["decision_id"] == decision["decision_id"]
    assert last_row["current_decision_id"] == decision["decision_id"]
    assert last_row["selected_option_id"] == selected_option_id
    assert last_row["action_count"] == 5
    assert last_row["action_completion"] == 1
    assert last_row["simulated_observation_count"] == 10
    assert last_row["observation_kind"] == "simulated"
    assert last_row["scenario_effective_time"] == decision["scenario_effective_time"]
    assert last_row["projection_refresh_time"] is not None
    assert variance_rows["response_cost"] == pytest.approx((25000 - 24750) / 24750)
    assert variance_rows["remaining_alpha_recovery_date"] is None
