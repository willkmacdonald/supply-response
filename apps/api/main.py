"""Supply Response API.

Run locally::

    uvicorn apps.api.main:app --reload --port 8000

The API never talks to Fabric, Foundry, or Work IQ in local mode: reference data
comes from the deterministic synthetic generator and application state is stored
in SQLite.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.database import init_db
from apps.api.routers import cases, dashboard
from data.schemas.models import SCHEMA_VERSION
from services.exposure.calculator import CALCULATION_VERSION
from services.policy.checker import POLICY_VERSION
from services.scenarios.evaluator import EVALUATOR_VERSION

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="Supply Response API",
    version=API_VERSION,
    lifespan=lifespan,
    description=(
        "Deterministic supply-disruption response API. All data is fictional and "
        "prefixed with RL-."
    ),
)

_origins = os.getenv("SUPPLY_RESPONSE_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(dashboard.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "policy_version": POLICY_VERSION,
    }
