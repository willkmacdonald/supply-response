# Isolate runtime provenance by Disruption Case

Each Disruption Case uses exactly one immutable runtime mode: live or fallback. Switching modes creates a new Case Instance rather than combining Work IQ/Fabric state with synthetic/SQLite state. This costs some duplicated case history, but it makes provenance, acceptance claims, and audit interpretation unambiguous; fallback also excludes Power BI because Power BI's authoritative source is Fabric.
