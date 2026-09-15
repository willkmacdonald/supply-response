"""Preview presenter history cleanup; use --apply to apply that exact preview."""

import argparse
import json
from dataclasses import asdict

from apps.api.app.settings import Settings
from services.persistence.store import build_store


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    # BaseSettings loads required fields from the configured environment.
    settings = Settings()  # pyright: ignore[reportCallIssue]
    store = build_store(settings)
    plan = store.preview_presenter_retention(historical_limit=3)
    print(json.dumps(asdict(plan), indent=2, sort_keys=True))
    if args.apply:
        result = store.apply_presenter_retention(plan)
        print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
