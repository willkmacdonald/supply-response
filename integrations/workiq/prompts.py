from __future__ import annotations


def _prompt(*, source_id: str, purpose: str, fields: str) -> str:
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 512:
        raise ValueError("Demo Corpus source ID is invalid")
    return f"""DEMO CORPUS — FICTIONAL
Retrieve only the Microsoft 365 tenant artifact with exact opaque source ID: {source_id}
Purpose: {purpose}.
Return explicit JSON facts containing only these fields: {fields}.
Attach a tenant citation with source ID, source timestamp, exact excerpt, and navigable deep link to every fact.
Do not infer, calculate, combine, or fill missing facts. Do not use web grounding or public web sources.
If the exact artifact or citation is unavailable, return that it is unavailable without inventing a fact or citation.
"""


def supplier_signal_prompt(source_id: str) -> str:
    return _prompt(
        source_id=source_id,
        purpose="supplier signal from RL-Supplier Alpha for the RL-001 order disruption",
        fields=(
            "supplier, affected quantity, offered quantity, offered date, "
            "unit expedite cost, and remaining quantity commitment"
        ),
    )


def quality_context_prompt(source_id: str) -> str:
    return _prompt(
        source_id=source_id,
        purpose="Quality context authored by Jordan for RL-Supplier Beta",
        fields=(
            "qualification state, audit state, first-article state, and next "
            "fictional-scenario review date"
        ),
    )
