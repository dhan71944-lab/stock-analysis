"""Calculate stock betas against the S&P 500 index from return CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BetaResult:
    ticker: str
    yahoo_symbol: str
    company: str
    sector: str
    observations: int
    beta: float


def read_index_returns(path: str | Path) -> dict[str, float]:
    returns: dict[str, float] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require_columns(reader, {"date", "daily_return"}, path)
        for row in reader:
            if row["daily_return"]:
                returns[row["date"]] = float(row["daily_return"])
    return returns


def calculate_betas(
    index_csv: str | Path,
    constituents_csv: str | Path,
    min_observations: int = 2,
) -> list[BetaResult]:
    index_returns = read_index_returns(index_csv)
    if not index_returns:
        raise RuntimeError("No index returns found.")

    grouped_returns: dict[str, list[tuple[float, float]]] = defaultdict(list)
    metadata: dict[str, dict[str, str]] = {}

    with Path(constituents_csv).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require_columns(
            reader,
            {
                "ticker",
                "yahoo_symbol",
                "company",
                "sector",
                "date",
                "daily_return",
            },
            constituents_csv,
        )
        for row in reader:
            stock_return = row["daily_return"]
            index_return = index_returns.get(row["date"])
            if not stock_return or index_return is None:
                continue

            ticker = row["ticker"]
            metadata.setdefault(
                ticker,
                {
                    "yahoo_symbol": row["yahoo_symbol"],
                    "company": row["company"],
                    "sector": row["sector"],
                },
            )
            grouped_returns[ticker].append((float(stock_return), index_return))

    results: list[BetaResult] = []
    for ticker, return_pairs in grouped_returns.items():
        if len(return_pairs) < min_observations:
            continue
        beta = calculate_beta(return_pairs)
        ticker_metadata = metadata[ticker]
        results.append(
            BetaResult(
                ticker=ticker,
                yahoo_symbol=ticker_metadata["yahoo_symbol"],
                company=ticker_metadata["company"],
                sector=ticker_metadata["sector"],
                observations=len(return_pairs),
                beta=beta,
            )
        )

    return sorted(results, key=lambda item: item.ticker)


def calculate_beta(return_pairs: list[tuple[float, float]]) -> float:
    stock_returns = [stock_return for stock_return, _ in return_pairs]
    index_returns = [index_return for _, index_return in return_pairs]

    average_stock_return = sum(stock_returns) / len(stock_returns)
    average_index_return = sum(index_returns) / len(index_returns)

    covariance = sum(
        (stock_return - average_stock_return) * (index_return - average_index_return)
        for stock_return, index_return in return_pairs
    ) / len(return_pairs)
    index_variance = sum(
        (index_return - average_index_return) ** 2 for index_return in index_returns
    ) / len(index_returns)

    if index_variance == 0:
        raise RuntimeError("Index return variance is zero; beta is undefined.")

    return covariance / index_variance


def write_betas_csv(results: list[BetaResult], output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "yahoo_symbol",
                "company",
                "sector",
                "observations",
                "beta",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "ticker": result.ticker,
                    "yahoo_symbol": result.yahoo_symbol,
                    "company": result.company,
                    "sector": result.sector,
                    "observations": str(result.observations),
                    "beta": format_beta(result.beta),
                }
            )


def require_columns(
    reader: csv.DictReader,
    expected_columns: set[str],
    path: str | Path,
) -> None:
    if not reader.fieldnames or not expected_columns.issubset(reader.fieldnames):
        missing = sorted(expected_columns - set(reader.fieldnames or []))
        raise RuntimeError(f"{path} is missing required columns: {missing}")


def format_beta(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate S&P 500 constituent betas from return CSVs."
    )
    parser.add_argument(
        "--index-csv",
        default="data/sp500_daily.csv",
        help="Index OHLCV/return CSV path. Defaults to data/sp500_daily.csv.",
    )
    parser.add_argument(
        "--constituents-csv",
        default="data/sp500_constituents_daily.csv",
        help=(
            "Constituent OHLCV/return CSV path. Defaults to "
            "data/sp500_constituents_daily.csv."
        ),
    )
    parser.add_argument(
        "--output",
        default="data/sp500_constituent_betas.csv",
        help="Output beta CSV path. Defaults to data/sp500_constituent_betas.csv.",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=2,
        help="Minimum matched return observations required per stock.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results = calculate_betas(
        index_csv=args.index_csv,
        constituents_csv=args.constituents_csv,
        min_observations=args.min_observations,
    )
    write_betas_csv(results, args.output)
    print(f"Wrote {len(results)} stock betas to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
