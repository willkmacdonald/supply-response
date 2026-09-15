def _approved_decision(client, services):
    created = client.post(
        "/api/cases",
        json={"template_id": "RL-001", "purpose": "automated_test"},
    )
    analysis = client.post(f"/api/cases/{created.json()['case_id']}/analysis")
    decision = client.post(
        f"/api/cases/{created.json()['case_id']}/decisions",
        headers={"Idempotency-Key": "RL-REVIEWED-EMAIL-API"},
        json={
            "analysis_id": analysis.json()["analysis_id"],
            "kind": "approved",
            "selected_option_id": "RL-OPTION-COMBINED",
        },
    )
    services.run_worker_until_idle()
    return decision.json()["decision_id"]


def test_reviewed_email_routes_version_and_review_without_sending(client, services):
    decision_id = _approved_decision(client, services)

    initial = client.get(f"/api/decisions/{decision_id}/supplier-email")

    assert initial.status_code == 200, initial.text
    assert initial.json()["revision"] == 1
    assert initial.json()["from_address"] == "agent@willmacdonald.com"
    assert initial.json()["to_address"] == "will@willmacdonald.com"
    assert initial.json()["send_status"] == "draft"
    edited = client.put(
        f"/api/decisions/{decision_id}/supplier-email",
        json={
            "revision": 1,
            "subject": "Updated supplier recovery request",
            "body": "Updated fictional demo body.",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == 2
    assert edited.json()["reviewed_revision"] is None
    reviewed = client.post(
        f"/api/decisions/{decision_id}/supplier-email/review",
        json={"revision": 2},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewed_revision"] == 2
    assert reviewed.json()["reviewed_by"]["persona_id"] == "RL-PERSONA-ALEX"
    assert reviewed.json()["send_status"] == "draft"
    assert (
        client.post(
            f"/api/decisions/{decision_id}/supplier-email/send",
            json={"revision": 2},
        ).status_code
        == 404
    )


def test_reviewed_email_request_never_accepts_delivery_fields(client, services):
    decision_id = _approved_decision(client, services)
    path = f"/api/decisions/{decision_id}/supplier-email"
    client.get(path)

    for field, value in (
        ("to_address", "attacker@example.com"),
        ("from_address", "attacker@example.com"),
        ("cc", ["attacker@example.com"]),
        ("bcc", ["attacker@example.com"]),
        ("attachments", [{"name": "payload.bin"}]),
    ):
        response = client.put(
            path,
            json={
                "revision": 1,
                "subject": "Safe subject",
                "body": "Safe body",
                field: value,
            },
        )
        assert response.status_code == 422, (field, response.text)
    current = client.get(path).json()
    assert current["revision"] == 1
    assert current["from_address"] == "agent@willmacdonald.com"
    assert current["to_address"] == "will@willmacdonald.com"


def test_reviewed_email_returns_safe_validation_and_conflict_responses(
    client, services
):
    decision_id = _approved_decision(client, services)
    path = f"/api/decisions/{decision_id}/supplier-email"
    client.get(path)

    for subject, body in (
        (" ", "body"),
        ("x" * 256, "body"),
        ("subject", " "),
        ("subject", "x" * 10_001),
    ):
        invalid = client.put(
            path,
            json={"revision": 1, "subject": subject, "body": body},
        )
        assert invalid.status_code == 422
        assert "traceback" not in invalid.text.lower()

    changed = client.put(
        path,
        json={"revision": 1, "subject": "Changed", "body": "Changed body"},
    )
    assert changed.status_code == 200
    stale = client.put(
        path,
        json={"revision": 1, "subject": "Again", "body": "Again body"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["message"] == (
        "The supplier email changed. Refresh it and try again."
    )
    stale_review = client.post(f"{path}/review", json={"revision": 1})
    assert stale_review.status_code == 409
    assert "traceback" not in stale_review.text.lower()
