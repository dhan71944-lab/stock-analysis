"""Calculate CAPM theoretical daily returns for stock return rows."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    from analysis.calculate_sp500_betas import (
        format_beta,
        read_index_returns,
        require_columns,
    )
except ModuleNotFoundError:
    from calculate_sp500_betas import format_beta, read_index_returns, require_columns


DEFAULT_RF_DAILY = 0.0001747


def read_betas(path: str | Path) -> dict[str, float]:
    betas: dict[str, float] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require_columns(reader, {"ticker", "beta"}, path)
        for row in reader:
            if row["beta"]:
                betas[row["ticker"]] = float(row["beta"])
    return betas


def write_capm_daily_returns_csv(
    index_csv: str | Path,
    constituents_csv: str | Path,
    betas_csv: str | Path,
    output_path: str | Path,
    rf_daily: float = DEFAULT_RF_DAILY,
) -> int:
    index_returns = read_index_returns(index_csv)
    betas = read_betas(betas_csv)
    if not index_returns:
        raise RuntimeError("No index returns found.")
    if not betas:
        raise RuntimeError("No stock betas found.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with Path(constituents_csv).open(newline="", encoding="utf-8") as input_handle:
        reader = csv.DictReader(input_handle)
        require_columns(reader, {"ticker", "date", "daily_return"}, constituents_csv)
        fieldnames = list(reader.fieldnames or [])
        extra_columns = [
            "index_daily_return",
            "rf_daily",
            "beta",
            "theoretical_daily_return",
        ]
        for column in extra_columns:
            if column not in fieldnames:
                fieldnames.append(column)

        with output.open("w", newline="", encoding="utf-8") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                ticker = row["ticker"]
                index_return = index_returns.get(row["date"])
                beta = betas.get(ticker)
                if index_return is None or beta is None:
                    continue

                theoretical_return = rf_daily + beta * (index_return - rf_daily)
                row["index_daily_return"] = format_beta(index_return)
                row["rf_daily"] = format_beta(rf_daily)
                row["beta"] = format_beta(beta)
                row["theoretical_daily_return"] = format_beta(theoretical_return)
                writer.writerow(row)
                rows_written += 1

    return rows_written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate CAPM theoretical daily returns for stock rows."
    )
    parser.add_argument("--index-csv", default="data/sp500_daily.csv")
    parser.add_argument(
        "--constituents-csv",
        default="data/sp500_constituents_daily.csv",
    )
    parser.add_argument("--betas-csv", default="data/sp500_constituent_betas.csv")
    parser.add_argument(
        "--output",
        default="data/sp500_constituents_capm_daily_returns.csv",
    )
    parser.add_argument(
        "--rf-daily",
        type=float,
        default=DEFAULT_RF_DAILY,
        help="Daily risk-free rate. Defaults to 0.0001747.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    rows = write_capm_daily_returns_csv(
        index_csv=args.index_csv,
        constituents_csv=args.constituents_csv,
        betas_csv=args.betas_csv,
        output_path=args.output,
        rf_daily=args.rf_daily,
    )
    print(f"Wrote {rows} CAPM daily return rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
