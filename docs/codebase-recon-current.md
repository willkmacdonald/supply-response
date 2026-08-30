# Codebase Recon Report — Current Main

Generated from `main` at commit `302a9ea` after the local-first GitHub integration.

## Scope and Interpretation

This report analyzes Git history. It identifies files with concentrated change activity; it does not determine whether a file is defective or whether it satisfies the project acceptance criteria.

All six files identified below as high-risk existed in the original local Codex base at `83bf7f6`. Neither GitHub donor commit is an ancestor of current `main`. The hotspot signal therefore reflects locally reviewed integration work, not wholesale import of the GitHub Copilot implementation.

## Repo Vitals

- Age: 2026-08-25 to 2026-08-30
- Commits: 14
- Branches: 5
- Analysis window: all time

## 1. Code Hotspots

1. `data/synthetic/generator.py` — 5 changes
2. `tests/test_evaluation_cases.py` — 4 changes
3. `tests/test_api.py` — 4 changes
4. `data/schemas/models.py` — 4 changes
5. `tests/test_generator.py` — 3 changes
6. `services/scenarios/evaluator.py` — 3 changes
7. `apps/web/src/types.ts` — 3 changes
8. `apps/api/app/main.py` — 3 changes
9. `.gitignore` — 3 changes

## 2. Bug Magnets

1. `tests/test_generator.py` — 2 fix-associated changes
2. `data/synthetic/generator.py` — 2 fix-associated changes
3. `tests/test_evaluation_cases.py` — 1 fix-associated change
4. `tests/test_documentation.py` — 1 fix-associated change
5. `tests/test_api.py` — 1 fix-associated change
6. `services/scenarios/evaluator.py` — 1 fix-associated change
7. `docs/superpowers/specs/2026-08-30-local-first-github-integration-design.md` — 1 fix-associated change
8. `docs/superpowers/plans/2026-08-30-milestone-1-domain-alignment.md` — 1 fix-associated change
9. `docs/codebase-recon-report.md` — 1 fix-associated change
10. `data/schemas/models.py` — 1 fix-associated change

## 3. High-Risk Files

These files appear in both the hotspot and bug-magnet lists:

- `data/synthetic/generator.py` — hotspot #1, bug magnet #2; primary owner: `willkmacdonald`
- `tests/test_evaluation_cases.py` — hotspot #2, bug magnet #3; primary owner: `willkmacdonald`
- `tests/test_api.py` — hotspot #3, bug magnet #5; primary owner: `willkmacdonald`
- `data/schemas/models.py` — hotspot #4, bug magnet #10; primary owner: `willkmacdonald`
- `tests/test_generator.py` — hotspot #5, bug magnet #1; primary owner: `willkmacdonald`
- `services/scenarios/evaluator.py` — hotspot #6, bug magnet #6; primary owner: `willkmacdonald`

## 4. Bus Factor

- `willkmacdonald` — 13 commits
- `OpenAI` — 1 commit
- Active in the last three months: 2 of 2 recorded contributors

The active-contributor ratio is not low, but practical knowledge ownership is concentrated in one human, which is expected for this project.

## 5. Team Momentum

- 2026-08 — 14 commits
- Trend: insufficient history to classify meaningfully

## 6. Firefighting Frequency

No revert, hotfix, emergency, or rollback commits were found.

- Emergency commits: 0 of 14
- Rate: 0%

## 7. Recently Added Files

The following files are tied at one introduction each:

- `tests/test_remaining_evaluation_cases.py`
- `tests/test_generator.py`
- `tests/test_exposure.py`
- `tests/test_evaluation_cases.py`
- `tests/test_evaluation_assets.py`
- `tests/test_documentation.py`
- `tests/test_api.py`
- `services/scenarios/evaluator.py`
- `services/scenarios/__init__.py`
- `services/policy/thresholds.py`

## 8. Recommendations

- Start reading: `data/synthetic/generator.py`, `services/scenarios/evaluator.py`, and `tests/test_evaluation_cases.py`.
- Ownership: `willkmacdonald`.
- Watch out: the repository is only six days old, and most changes occurred during one integration effort. Churn and fix-associated results identify integration pressure points, not mature production defect patterns.
- Strongest current risk seam: the relationship between synthetic data generation, scenario evaluation, API contracts, and evaluation-case tests.
- Next analysis: inventory the current architecture and executable evaluations, then produce a separate acceptance-criteria traceability report.
