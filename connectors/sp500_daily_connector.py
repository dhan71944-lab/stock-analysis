"""Download daily S&P 500 price history.

The S&P 500 is an index, not a NYSE-listed security. NYSE's official
historical feeds are licensed data products, so this connector defaults to a
public daily OHLCV source for the S&P 500 index and keeps the download logic
isolated behind a small connector API.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"


@dataclass(frozen=True)
class DownloadResult:
    symbol: str
    start: dt.date | None
    end: dt.date | None
    rows: int
    output_path: Path


class Sp500DailyConnector:
    """Connector for daily S&P 500 index OHLCV data."""

    def __init__(self, symbol: str = "^GSPC", timeout: int = 30) -> None:
        self.symbol = symbol
        self.timeout = timeout

    def download_csv(
        self,
        output_path: str | Path,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> DownloadResult:
        """Download daily data and write it as a normalized CSV file.

        Output columns:
            date, open, high, low, close, volume, daily_return
        """

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        request = urllib.request.Request(
            self._build_url(start=start, end=end),
            headers={"User-Agent": "stock-analysis-connector/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = response.read().decode("utf-8")

        rows = self._parse_rows(payload)
        if not rows:
            raise RuntimeError("No S&P 500 rows were returned by the data source.")

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "daily_return",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        return DownloadResult(
            symbol=self.symbol,
            start=start,
            end=end,
            rows=len(rows),
            output_path=output,
        )

    def _build_url(
        self,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> str:
        query = {
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        if start:
            query["period1"] = str(date_to_unix(start))
        else:
            query["period1"] = "0"
        if end:
            # Yahoo's period2 is exclusive, so add one day to include end.
            query["period2"] = str(date_to_unix(end + dt.timedelta(days=1)))
        else:
            query["period2"] = str(date_to_unix(dt.date.today() + dt.timedelta(days=1)))

        symbol = urllib.parse.quote(self.symbol, safe="")
        return f"{YAHOO_CHART_URL}{symbol}?{urllib.parse.urlencode(query)}"

    @staticmethod
    def _parse_rows(payload: str) -> list[dict[str, str]]:
        data = json.loads(payload)
        result = data.get("chart", {}).get("result")
        if not result:
            error = data.get("chart", {}).get("error")
            raise RuntimeError(f"No chart data returned by the data source: {error}")

        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = (chart.get("indicators", {}).get("quote") or [{}])[0]

        required = ["open", "high", "low", "close", "volume"]
        if not timestamps or not all(name in quote for name in required):
            raise RuntimeError("Unexpected JSON format returned by the data source.")

        rows: list[dict[str, str]] = []
        previous_close: float | None = None
        for index, timestamp in enumerate(timestamps):
            values = {name: quote[name][index] for name in required}
            if any(values[name] is None for name in required):
                continue
            close = float(values["close"])
            daily_return = ""
            if previous_close is not None:
                daily_return = format_return((close - previous_close) / previous_close)
            rows.append(
                {
                    "date": dt.datetime.fromtimestamp(
                        timestamp, tz=dt.timezone.utc
                    ).date().isoformat(),
                    "open": format_decimal(values["open"]),
                    "high": format_decimal(values["high"]),
                    "low": format_decimal(values["low"]),
                    "close": format_decimal(values["close"]),
                    "volume": str(int(values["volume"])),
                    "daily_return": daily_return,
                }
            )
            previous_close = close
        return rows


def date_to_unix(value: dt.date) -> int:
    return int(dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc).timestamp())


def format_decimal(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_return(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    return dt.date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download daily S&P 500 index OHLCV data to CSV."
    )
    parser.add_argument(
        "--output",
        default="data/sp500_daily.csv",
        help="CSV output path. Defaults to data/sp500_daily.csv.",
    )
    parser.add_argument("--start", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--symbol",
        default="^GSPC",
        help="Source symbol. Defaults to ^GSPC for the S&P 500 index.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    connector = Sp500DailyConnector(symbol=args.symbol)
    result = connector.download_csv(
        output_path=args.output,
        start=parse_date(args.start),
        end=parse_date(args.end),
    )

    print(
        f"Downloaded {result.rows} {result.symbol} daily rows "
        f"to {result.output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
