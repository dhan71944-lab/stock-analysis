# Project Agent Instructions

## Project Purpose

This repository contains lightweight stock-analysis utilities, starting with a
daily S&P 500 index data connector that writes normalized CSV output for later
analysis.

## Setup

Use the Python standard library unless a task clearly needs an added
dependency.

```powershell
python .\connectors\sp500_daily_connector.py --start 2024-01-01 --end 2024-12-31 --output .\data\sp500_daily.csv
```

If `python` is not on `PATH` in Codex, use the bundled runtime:

```powershell
& 'C:\Users\DhanyaGB\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\connectors\sp500_daily_connector.py --start 2024-01-01 --end 2024-12-31 --output .\data\sp500_daily.csv
```

## Architecture

- `connectors/`: source-specific data download code.
- `data/`: generated CSV outputs; keep these local and out of git unless the
  user explicitly asks to version a fixture.

## Conventions

- dependency manager: none yet
- test runner: Python `unittest` or focused CLI verification until a test suite
  is added
- formatter/linter: none yet; keep code PEP 8 friendly
- type checker: none yet; keep public function signatures typed
- local dev server: none

## Safety Rules

- Do not commit generated market data files from `data/`.
- Do not commit API keys, paid data-feed credentials, `.env` files, OAuth
  tokens, or local GitHub tooling.
- Treat licensed exchange data and paid market-data feeds as sensitive; ask
  before adding credentials, redistribution logic, or vendor-specific config.
- Preserve the distinction between the S&P 500 index and NYSE-listed equities
  in docs and code comments.

## Definition Of Done

- connector changes run successfully for a small date range, or the network
  limitation is clearly stated
- syntax is checked with `python -m py_compile` or equivalent
- README or usage notes are updated when commands, outputs, or data sources
  change
- `git status` is reviewed so generated data and local setup files are not
  staged accidentally
