# Fabric layer

Fabric is the primary operational-data layer for the hosted demo. Everything in
this folder is optional for local development: the local stack runs entirely on
the synthetic generator and SQLite.

| Folder | Contents |
|---|---|
| `sql/` | `schema.sql` (table DDL, generated from `data/schemas/models.py`) and `calculations.sql` (portable exposure query) |
| `notebooks/` | `load_synthetic_data.py` — Fabric notebook that writes the synthetic dataset into the lakehouse |
| `semantic-model/` | `model.json` — tables, relationships, and measures for the semantic model |
| `ontology/` | `entities.json` — Fabric IQ entities and governed relationships |
| `power-bi/` | Report page definitions (`report-pages.md`) |

## Go/no-go

Fabric IQ stays optional until September 11. If any go/no-go check fails, remove
only the live ontology/MCP dependency; Fabric tables, dashboards, and the web
application remain.
