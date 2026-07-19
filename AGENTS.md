# Repository Guidelines

## Project Structure & Module Organization

The package lives under `src/gpr_engine/`. Keep production data access in `ingest/` and `econometrics/dataset.py`; file- and FRED-based research loaders belong in `econometrics/data_files.py`. Experimental formulas stay in `econometrics/` until they pass the documented research gates.

Tests mirror the package in `tests/`, with econometrics tests in `tests/econ/`. Research runners are in `scripts/`, SQL migrations in `sql/`, locked parameters in `config/`, notebooks in `notebooks/`, and governance documents in `docs/`. Versioned outputs belong in `docs/reports/`; source data and caches belong in `data/` and are ignored by Git.

## Build, Test, and Development Commands

Use Python 3.11 or newer. Do not modify `.venv`; invoke Python directly.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest tests/econ/test_shocks.py -x
python -m ruff check .
python scripts/run_e0_replication.py
jupyter lab notebooks/01_explore.ipynb
```

The first command installs development dependencies. Run the full suite before submitting; use focused pytest while iterating. Research scripts may consume files in `data/` or cached external series, so check their arguments first.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and `UPPER_CASE` constants. Add type hints to public interfaces and short docstrings that state data frequency, units, and return shape. Keep transformations centralized in `econometrics/dataset.py`; do not duplicate them in offline loaders. Ruff is the repository linter.

## Testing Guidelines

Pytest is the test framework. Name files `test_<subject>.py` and tests `test_<behavior>()`. Formula and econometrics changes require deterministic unit tests, including no-lookahead and missing-data cases. Mock file/network I/O where possible. Changes to `config/backtest.yaml` or `config/hypothesis_registry.yaml` must update their matching lock tests in the same commit.

## Commit & Pull Request Guidelines

History favors small, phase-scoped commits; use an imperative `<phase or scope>: <outcome>` subject (for example, `F4: enforce the backtest lock`) instead of vague `update` messages. Pull requests should explain the hypothesis or behavior changed, list validation commands and results, link the governing document or issue, and identify affected data/config versions. Include report or figure paths when outputs change; avoid unrelated refactors.

## Security & Agent Instructions

Never commit secrets, `.env`, raw spreadsheets, CSV exports, or `data/cache/`. Do not read or edit `.env`, `.env.dev`, or `.env.prod`; document configuration only in `.env.example`. Treat the final holdout and locked research registry as governed artifacts, not ordinary tuning inputs.
