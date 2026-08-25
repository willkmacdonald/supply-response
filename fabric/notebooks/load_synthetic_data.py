"""Fabric notebook: load the Supply Response synthetic dataset into a lakehouse.

Run this as a Fabric notebook attached to a lakehouse. Locally it is a plain
Python script that writes Parquet/CSV files instead, so the same code path can be
tested without a Fabric capacity.

The dataset is deterministic: the same seed always produces the same tables.
"""

# MAGIC %pip install pydantic>=2

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.schemas.models import TABLE_NAMES  # noqa: E402
from data.synthetic.generator import DEFAULT_SEED, generate_dataset  # noqa: E402

SEED = DEFAULT_SEED
LAKEHOUSE_TABLE_PREFIX = "supply_response_"
LOCAL_OUTPUT_DIR = REPO_ROOT / "data" / "synthetic" / "tables"


def _rows(dataset, table_name: str) -> list[dict]:
    return [row.model_dump(mode="json") for row in dataset.table(table_name)]


def load_to_fabric(seed: int = SEED) -> None:
    """Write every table into the attached lakehouse as a managed Delta table."""
    from pyspark.sql import SparkSession  # type: ignore[import-not-found]

    spark = SparkSession.builder.getOrCreate()
    dataset = generate_dataset(seed)
    for table_name in TABLE_NAMES:
        rows = _rows(dataset, table_name)
        if not rows:
            continue
        spark.createDataFrame(rows).write.mode("overwrite").saveAsTable(
            f"{LAKEHOUSE_TABLE_PREFIX}{table_name}"
        )
        print(f"wrote {LAKEHOUSE_TABLE_PREFIX}{table_name}: {len(rows)} rows")


def load_to_local(seed: int = SEED, output_dir: Path = LOCAL_OUTPUT_DIR) -> Path:
    """Fallback used when no Spark session is available."""
    import json

    dataset = generate_dataset(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    for table_name in TABLE_NAMES:
        path = output_dir / f"{table_name}.json"
        path.write_text(json.dumps(_rows(dataset, table_name), indent=2), encoding="utf-8")
        print(f"wrote {path}")
    return output_dir


if __name__ == "__main__":
    try:
        load_to_fabric()
    except Exception as error:  # pragma: no cover - Fabric-only path
        print(f"Spark unavailable ({error}); writing local JSON tables instead.")
        load_to_local()
