from decimal import Decimal

DEFAULT_PREMIUM_FREIGHT_APPROVAL_THRESHOLD = Decimal("20000")


def requires_finance_approval(response_cost: Decimal, threshold: Decimal = DEFAULT_PREMIUM_FREIGHT_APPROVAL_THRESHOLD) -> bool:
    return response_cost > threshold


from datetime import date, timedelta


def collaboration_evidence_is_stale(*, evidence_date: date | None, as_of: date, max_age_days: int = 14) -> bool:
    return evidence_date is None or evidence_date < as_of - timedelta(days=max_age_days)


def dates_conflict(*, communicated_date: date | None, operational_date: date | None) -> bool:
    return communicated_date is not None and operational_date is not None and communicated_date != operational_date
