"""SQLAlchemy setup for the local SQLite database.

Only application state is persisted here (disruption cases, evaluated scenarios,
the action ledger and outcomes). Operational reference data comes from the
synthetic dataset provider in :mod:`apps.api.dataset`, which keeps the storage
contract portable to Fabric later.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "supply_response.db"
DATABASE_URL = os.getenv("SUPPLY_RESPONSE_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")

_connect_args: dict[str, Any] = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseRecord(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    disruption_id: Mapped[str] = mapped_column(String(32), index=True)
    supplier_id: Mapped[str] = mapped_column(String(32))
    part_id: Mapped[str] = mapped_column(String(32))
    plant_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    severity: Mapped[str] = mapped_column(String(16), default="high")
    signal_reference: Mapped[str] = mapped_column(String(255), default="")
    signal_received_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    horizon_start: Mapped[Any] = mapped_column(Date)
    horizon_end: Mapped[Any] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(String(128), default="Alex Morgan")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disruption: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    exposure: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    revenue_at_risk: Mapped[float] = mapped_column(Float, default=0.0)
    margin_at_risk: Mapped[float] = mapped_column(Float, default=0.0)
    otif_lines_at_risk: Mapped[int] = mapped_column(Integer, default=0)

    scenarios: Mapped[list["ScenarioRecord"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ScenarioRecord.rank"
    )
    actions: Mapped[list["ActionRecord"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ActionRecord.decided_at"
    )


class ScenarioRecord(Base):
    __tablename__ = "case_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(32), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    executable: Mapped[bool] = mapped_column(Integer, default=1)
    recommended: Mapped[bool] = mapped_column(Integer, default=0)
    response_cost: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_protected: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    case: Mapped[CaseRecord] = relationship(back_populates="scenarios")


class ActionRecord(Base):
    __tablename__ = "action_ledger"

    action_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    disruption_id: Mapped[str] = mapped_column(String(32), index=True)
    scenario_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    decided_by: Mapped[str] = mapped_column(String(128))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    rationale: Mapped[str] = mapped_column(Text, default="")
    calculation_version: Mapped[str] = mapped_column(String(16), default="")
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    follow_up_tasks: Mapped[list[str]] = mapped_column(JSON, default=list)
    predicted_cost: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_revenue_protected: Mapped[float] = mapped_column(Float, default=0.0)

    case: Mapped[CaseRecord] = relationship(back_populates="actions")


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


__all__ = [
    "ActionRecord",
    "Base",
    "CaseRecord",
    "DATABASE_URL",
    "ScenarioRecord",
    "SessionLocal",
    "engine",
    "get_session",
    "init_db",
]
