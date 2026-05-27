"""Download daily OHLCV and returns for current S&P 500 constituents."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

try:
    from connectors.sp500_daily_connector import (
        YAHOO_CHART_URL,
        date_to_unix,
        format_decimal,
        format_return,
        parse_date,
    )
except ModuleNotFoundError:
    from sp500_daily_connector import (
        YAHOO_CHART_URL,
        date_to_unix,
        format_decimal,
        format_return,
        parse_date,
    )


SP500_CONSTITUENTS_URL = (
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
)


@dataclass(frozen=True)
class Constituent:
    ticker: str
    yahoo_symbol: str
    company: str
    sector: str


@dataclass(frozen=True)
class ConstituentsDownloadResult:
    constituents: int
    rows: int
    output_path: Path
    errors: tuple[str, ...]


class ConstituentsTableParser(HTMLParser):
    """Parse the current S&P 500 constituents table from Wikipedia HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.in_constituents_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "constituents":
            self.in_constituents_table = True
        if not self.in_constituents_table:
            return
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if not self.in_constituents_table:
            return
        if tag in {"td", "th"} and self.in_cell:
            self.current_row.append(clean_text("".join(self.current_cell)))
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif tag == "table":
            self.in_constituents_table = False

    def handle_data(self, data: str) -> None:
        if self.in_constituents_table and self.in_cell:
            self.current_cell.append(data)


class Sp500ConstituentsDailyConnector:
    """Connector for current S&P 500 constituent daily OHLCV and returns."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def download_csv(
        self,
        output_path: str | Path,
        start: dt.date | None = None,
        end: dt.date | None = None,
        limit: int | None = None,
        fail_fast: bool = False,
    ) -> ConstituentsDownloadResult:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        constituents = self.fetch_constituents()
        if limit is not None:
            constituents = constituents[:limit]

        rows_written = 0
        errors: list[str] = []
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=combined_fieldnames())
            writer.writeheader()
            for index, constituent in enumerate(constituents, start=1):
                print(
                    f"[{index}/{len(constituents)}] downloading "
                    f"{constituent.ticker}",
                    file=sys.stderr,
                )
                try:
                    rows = self.fetch_price_rows(
                        constituent=constituent,
                        start=start,
                        end=end,
                    )
                except Exception as exc:
                    message = f"{constituent.ticker}: {exc}"
                    if fail_fast:
                        raise RuntimeError(message) from exc
                    errors.append(message)
                    print(f"  skipped {message}", file=sys.stderr)
                    continue
                writer.writerows(rows)
                rows_written += len(rows)

        return ConstituentsDownloadResult(
            constituents=len(constituents),
            rows=rows_written,
            output_path=output,
            errors=tuple(errors),
        )

    def fetch_constituents(self) -> list[Constituent]:
        request = urllib.request.Request(
            SP500_CONSTITUENTS_URL,
            headers={"User-Agent": "stock-analysis-connector/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            html = response.read().decode("utf-8")

        parser = ConstituentsTableParser()
        parser.feed(html)
        if len(parser.rows) < 2:
            raise RuntimeError("Could not parse the S&P 500 constituents table.")

        header = parser.rows[0]
        symbol_index = header.index("Symbol")
        company_index = header.index("Security")
        sector_index = header.index("GICS Sector")

        constituents: list[Constituent] = []
        for row in parser.rows[1:]:
            if len(row) <= max(symbol_index, company_index, sector_index):
                continue
            ticker = row[symbol_index]
            constituents.append(
                Constituent(
                    ticker=ticker,
                    yahoo_symbol=ticker.replace(".", "-"),
                    company=row[company_index],
                    sector=row[sector_index],
                )
            )
        if not constituents:
            raise RuntimeError("No S&P 500 constituents were parsed.")
        return constituents

    def fetch_price_rows(
        self,
        constituent: Constituent,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> list[dict[str, str]]:
        request = urllib.request.Request(
            build_yahoo_chart_url(
                symbol=constituent.yahoo_symbol,
                start=start,
                end=end,
            ),
            headers={"User-Agent": "stock-analysis-connector/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = response.read().decode("utf-8")

        rows = parse_yahoo_rows(payload)
        for row in rows:
            row.update(
                {
                    "ticker": constituent.ticker,
                    "yahoo_symbol": constituent.yahoo_symbol,
                    "company": constituent.company,
                    "sector": constituent.sector,
                }
            )
        return rows


def build_yahoo_chart_url(
    symbol: str,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> str:
    query = {
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
        "period1": str(date_to_unix(start)) if start else "0",
        "period2": str(
            date_to_unix((end or dt.date.today()) + dt.timedelta(days=1))
        ),
    }
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    encoded_query = urllib.parse.urlencode(query)
    return f"{YAHOO_CHART_URL}{encoded_symbol}?{encoded_query}"


def parse_yahoo_rows(payload: str) -> list[dict[str, str]]:
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
                "ticker": "",
                "yahoo_symbol": "",
                "company": "",
                "sector": "",
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


def clean_text(value: str) -> str:
    return " ".join(value.split())


def combined_fieldnames() -> list[str]:
    return [
        "ticker",
        "yahoo_symbol",
        "company",
        "sector",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "daily_return",
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download daily OHLCV and returns for current S&P 500 constituents."
        )
    )
    parser.add_argument(
        "--output",
        default="data/sp500_constituents_daily.csv",
        help="CSV output path. Defaults to data/sp500_constituents_daily.csv.",
    )
    parser.add_argument("--start", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of constituents. Useful for smoke tests.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on the first ticker download error instead of skipping it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    connector = Sp500ConstituentsDailyConnector()
    result = connector.download_csv(
        output_path=args.output,
        start=parse_date(args.start),
        end=parse_date(args.end),
        limit=args.limit,
        fail_fast=args.fail_fast,
    )
    print(
        f"Downloaded {result.rows} rows for {result.constituents} current "
        f"S&P 500 constituents to {result.output_path}"
    )
    if result.errors:
        print(f"Skipped {len(result.errors)} tickers with errors.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
