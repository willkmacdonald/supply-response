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


def _normalized_row(payload: dict[str, object]) -> dict[str, object]:
    results = payload["results"]
    assert isinstance(results, list) and len(results) == 1
    tables = results[0]["tables"]
    assert isinstance(tables, list) and len(tables) == 1
    rows = tables[0]["rows"]
    assert isinstance(rows, list) and len(rows) == 1
    return {key.strip("[]"): value for key, value in rows[0].items()}


def test_latest_showcase_decision_reaches_power_bi_within_sixty_seconds() -> None:
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
    dax = f'''EVALUATE
ROW(
  "case_id", CALCULATE(SELECTEDVALUE(CaseCommandCenter[case_id]), CaseCommandCenter[case_id] = "{case["case_id"]}"),
  "decision_id", CALCULATE(SELECTEDVALUE(ActionOutcomes[decision_id]), ActionOutcomes[decision_id] = "{decision["decision_id"]}"),
  "selected_option_id", CALCULATE(SELECTEDVALUE(ActionOutcomes[selected_option_id]), ActionOutcomes[decision_id] = "{decision["decision_id"]}"),
  "action_count", CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[decision_id] = "{decision["decision_id"]}", ActionOutcomes[record_type] = "action"),
  "simulated_observation_count", CALCULATE(COUNTROWS(ActionOutcomes), ActionOutcomes[decision_id] = "{decision["decision_id"]}", ActionOutcomes[observation_kind] = "simulated"),
  "scenario_effective_time", CALCULATE(MAX(ActionOutcomes[scenario_effective_time]), ActionOutcomes[decision_id] = "{decision["decision_id"]}"),
  "projection_refresh_time", CALCULATE(MAX(ActionOutcomes[projection_updated_at]), ActionOutcomes[decision_id] = "{decision["decision_id"]}")
)'''

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

    assert last_row["case_id"] == case["case_id"]
    assert last_row["decision_id"] == decision["decision_id"]
    assert last_row["selected_option_id"] == selected_option_id
    assert last_row["action_count"] == 5
    assert last_row["simulated_observation_count"] == 10
    assert last_row["scenario_effective_time"] == decision["scenario_effective_time"]
    assert last_row["projection_refresh_time"] is not None
