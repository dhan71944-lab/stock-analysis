"""Command-line tool for S&P 500 data downloads and beta analysis.

This module is intentionally dependency-free so it can be invoked by people,
automation, schedulers, and agentic tools with a plain Python runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from analysis.calculate_sp500_betas import calculate_betas, write_betas_csv
from connectors.sp500_constituents_daily_connector import (
    Sp500ConstituentsDailyConnector,
)
from connectors.sp500_daily_connector import Sp500DailyConnector, parse_date


def command_download_index(args: argparse.Namespace) -> dict[str, Any]:
    connector = Sp500DailyConnector(symbol=args.symbol, timeout=args.timeout)
    result = connector.download_csv(
        output_path=args.output,
        start=parse_date(args.start),
        end=parse_date(args.end),
    )
    return {
        "command": "download-index",
        "symbol": result.symbol,
        "start": serialize_value(result.start),
        "end": serialize_value(result.end),
        "rows": result.rows,
        "output_path": str(result.output_path),
    }


def command_download_constituents(args: argparse.Namespace) -> dict[str, Any]:
    connector = Sp500ConstituentsDailyConnector(timeout=args.timeout)
    result = connector.download_csv(
        output_path=args.output,
        start=parse_date(args.start),
        end=parse_date(args.end),
        limit=args.limit,
        fail_fast=args.fail_fast,
    )
    return {
        "command": "download-constituents",
        "constituents": result.constituents,
        "rows": result.rows,
        "output_path": str(result.output_path),
        "errors": list(result.errors),
    }


def command_calculate_betas(args: argparse.Namespace) -> dict[str, Any]:
    results = calculate_betas(
        index_csv=args.index_csv,
        constituents_csv=args.constituents_csv,
        min_observations=args.min_observations,
    )
    write_betas_csv(results, args.output)
    return {
        "command": "calculate-betas",
        "betas": len(results),
        "index_csv": str(args.index_csv),
        "constituents_csv": str(args.constituents_csv),
        "output_path": str(args.output),
        "min_observations": args.min_observations,
    }


def command_run_beta_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    index_result = Sp500DailyConnector(
        symbol=args.symbol,
        timeout=args.timeout,
    ).download_csv(
        output_path=args.index_csv,
        start=parse_date(args.start),
        end=parse_date(args.end),
    )

    constituents_result = Sp500ConstituentsDailyConnector(
        timeout=args.timeout
    ).download_csv(
        output_path=args.constituents_csv,
        start=parse_date(args.start),
        end=parse_date(args.end),
        limit=args.limit,
        fail_fast=args.fail_fast,
    )

    beta_results = calculate_betas(
        index_csv=args.index_csv,
        constituents_csv=args.constituents_csv,
        min_observations=args.min_observations,
    )
    write_betas_csv(beta_results, args.output)

    return {
        "command": "run-beta-pipeline",
        "index": {
            "symbol": index_result.symbol,
            "rows": index_result.rows,
            "output_path": str(index_result.output_path),
        },
        "constituents": {
            "constituents": constituents_result.constituents,
            "rows": constituents_result.rows,
            "output_path": str(constituents_result.output_path),
            "errors": list(constituents_result.errors),
        },
        "betas": {
            "rows": len(beta_results),
            "output_path": str(args.output),
            "min_observations": args.min_observations,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-analysis-tool",
        description="Download S&P 500 data and calculate constituent betas.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON result to stdout.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser(
        "download-index",
        help="Download S&P 500 index OHLCV and daily returns.",
    )
    add_date_args(index)
    index.add_argument("--symbol", default="^GSPC")
    index.add_argument("--timeout", type=int, default=30)
    index.add_argument("--output", default="data/sp500_daily.csv")
    index.set_defaults(handler=command_download_index)

    constituents = subparsers.add_parser(
        "download-constituents",
        help="Download OHLCV and daily returns for current S&P 500 constituents.",
    )
    add_date_args(constituents)
    add_constituent_args(constituents)
    constituents.add_argument("--output", default="data/sp500_constituents_daily.csv")
    constituents.set_defaults(handler=command_download_constituents)

    betas = subparsers.add_parser(
        "calculate-betas",
        help="Calculate stock betas from index and constituent return CSVs.",
    )
    add_beta_args(betas)
    betas.set_defaults(handler=command_calculate_betas)

    pipeline = subparsers.add_parser(
        "run-beta-pipeline",
        help="Download index data, download constituent data, and calculate betas.",
    )
    add_date_args(pipeline)
    add_constituent_args(pipeline)
    add_beta_args(pipeline)
    pipeline.add_argument("--symbol", default="^GSPC")
    pipeline.set_defaults(handler=command_run_beta_pipeline)

    return parser


def add_date_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format.")


def add_constituent_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--limit", type=int, help="Limit constituents for smoke tests.")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first ticker download error.",
    )


def add_beta_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--index-csv", default="data/sp500_daily.csv")
    parser.add_argument(
        "--constituents-csv",
        default="data/sp500_constituents_daily.csv",
    )
    parser.add_argument("--output", default="data/sp500_constituent_betas.csv")
    parser.add_argument("--min-observations", type=int, default=2)


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    command = result["command"]
    if command == "download-index":
        print(f"Downloaded {result['rows']} index rows to {result['output_path']}")
    elif command == "download-constituents":
        print(
            f"Downloaded {result['rows']} rows for "
            f"{result['constituents']} constituents to {result['output_path']}"
        )
        if result["errors"]:
            print(f"Skipped {len(result['errors'])} tickers with errors.")
    elif command == "calculate-betas":
        print(f"Wrote {result['betas']} stock betas to {result['output_path']}")
    elif command == "run-beta-pipeline":
        print(f"Downloaded {result['index']['rows']} index rows")
        print(
            f"Downloaded {result['constituents']['rows']} constituent rows "
            f"for {result['constituents']['constituents']} constituents"
        )
        print(
            f"Wrote {result['betas']['rows']} stock betas to "
            f"{result['betas']['output_path']}"
        )


def serialize_value(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = args.handler(args)
    except Exception as exc:
        error = {
            "command": getattr(args, "command", None),
            "error": str(exc),
            "type": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(error, indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_result(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
