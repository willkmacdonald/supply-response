# Microsoft Fabric JSON schemas

`microsoft/manifest.json` pins the official schemas used by the committed PBIP,
PBIR, TMDL item metadata, pages, and visual containers. Every catalog file is
content-addressed and SHA-256 verified before validation, so the normal test and
deployment preflight paths are deterministic and offline.

To review an upstream schema update, run:

```bash
uv run python fabric/schemas/update_microsoft_schemas.py
```

The updater accepts only exact HTTPS URLs on `developer.microsoft.com` at the default
port, rejects credentials, query strings, fragments, redirects, and final-URL
changes, recursively downloads schema references, removes stale content-addressed
files, and regenerates the manifest.
Review all version, manifest, and schema diffs; run
`tests/fabric/test_power_bi_project.py`; and commit the catalog only as an intentional
Microsoft schema-version update. The updater is never invoked by tests or deployment
preflight.

Preflight separately requires the exact approved root set and recomputes the
transitive `$ref` closure from the pinned files. Manifest URLs, files, and hashes must
equal that closure exactly; off-origin, unused, missing, duplicate, stale, or
path-escaping entries fail before artifact validation.
