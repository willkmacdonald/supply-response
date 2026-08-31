"""Refresh the pinned Microsoft Fabric JSON-schema catalog.

Run only when intentionally reviewing a Microsoft schema update:

    uv run python fabric/schemas/update_microsoft_schemas.py

The script downloads only developer.microsoft.com JSON schemas, follows their
transitive references, and writes a content-addressed manifest for offline tests.
Review the manifest and schema diff before committing an update.
"""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import urlopen


OUTPUT = Path(__file__).resolve().parent / "microsoft"
ROOT_SCHEMAS = (
    "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json",
)


def _references(value: object) -> list[str]:
    if isinstance(value, dict):
        found = [value["$ref"]] if isinstance(value.get("$ref"), str) else []
        for child in value.values():
            found.extend(_references(child))
        return found
    if isinstance(value, list):
        return [reference for child in value for reference in _references(child)]
    return []


def _fetch(url: str) -> dict[str, Any]:
    if urlparse(url).hostname != "developer.microsoft.com":
        raise ValueError(f"refusing non-Microsoft schema URL: {url}")
    with urlopen(url, timeout=30) as response:  # noqa: S310 - host is allowlisted above
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise TypeError(f"schema root must be an object: {url}")
    return value


def main() -> None:
    queue: deque[str] = deque(ROOT_SCHEMAS)
    schemas: dict[str, dict[str, Any]] = {}
    while queue:
        url = urldefrag(queue.popleft()).url
        if not url or url in schemas:
            continue
        schema = _fetch(url)
        schemas[url] = schema
        for reference in _references(schema):
            referenced_url = urldefrag(urljoin(url, reference)).url
            if referenced_url and referenced_url not in schemas:
                queue.append(referenced_url)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "source": "https://developer.microsoft.com/json-schemas/fabric/",
        "roots": list(ROOT_SCHEMAS),
        "schemas": {},
    }
    entries: dict[str, dict[str, str]] = {}
    for url, schema in sorted(schemas.items()):
        content = (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode()
        digest = hashlib.sha256(content).hexdigest()
        filename = f"{digest[:20]}.json"
        (OUTPUT / filename).write_bytes(content)
        entries[url] = {"file": filename, "sha256": digest}
    current_files = {entry["file"] for entry in entries.values()}
    for path in OUTPUT.glob("*.json"):
        if path.name != "manifest.json" and path.name not in current_files:
            path.unlink()
    manifest["schemas"] = entries
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Vendored {len(entries)} Microsoft schemas in {OUTPUT}")


if __name__ == "__main__":
    main()
