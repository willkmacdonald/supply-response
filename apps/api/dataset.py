"""Reference-data provider for the API.

Locally the operational tables come from the deterministic synthetic generator
(or a previously generated JSON file). In Fabric the same contract would be
served by the SQL endpoint, so the rest of the application never depends on the
source.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from data.schemas.models import Dataset
from data.synthetic.generator import DEFAULT_SEED, generate_dataset, load_dataset

_override: Optional[Dataset] = None


@lru_cache(maxsize=1)
def _default_dataset() -> Dataset:
    dataset_path = os.getenv("SUPPLY_RESPONSE_DATASET")
    if dataset_path and Path(dataset_path).exists():
        return load_dataset(dataset_path)
    seed = int(os.getenv("SUPPLY_RESPONSE_SEED", str(DEFAULT_SEED)))
    return generate_dataset(seed)


def get_dataset() -> Dataset:
    """Return the active reference dataset."""
    return _override if _override is not None else _default_dataset()


def set_dataset(dataset: Optional[Dataset]) -> None:
    """Override the dataset (used by tests and demo mode)."""
    global _override
    _override = dataset


def reset_dataset() -> None:
    set_dataset(None)
    _default_dataset.cache_clear()


__all__ = ["get_dataset", "reset_dataset", "set_dataset"]
