from apps.api.app.auth import PersonaBinding


def test_taylor_binding_is_exact_and_finance_only():
    binding = PersonaBinding.taylor(
        "11111111-1111-4111-8111-111111111111",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )
    assert binding.persona_id == "RL-PERSONA-TAYLOR"
    assert binding.allowed_roles == ("finance_approver",)
    assert binding.source_id == "RL-ENTRA-TAYLOR"
