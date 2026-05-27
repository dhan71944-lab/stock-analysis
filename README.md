# Stock Analysis Connectors

This workspace contains a small connector for downloading daily S&P 500 index
price history and close-to-close daily returns as CSV.

## S&P 500 daily connector

Run:

```powershell
python .\connectors\sp500_daily_connector.py --start 2024-01-01 --end 2024-12-31 --output .\data\sp500_daily.csv
```

Output columns:

```text
date, open, high, low, close, volume, daily_return
```

Daily return is calculated as:

```text
(close_t - close_t_minus_1) / close_t_minus_1
```

The first row's `daily_return` is blank because there is no prior close in the
downloaded series.

The default symbol is `^GSPC`, which represents the S&P 500 index. You can
override it with `--symbol` if your upstream data source uses a different code.

## S&P 500 constituents daily connector

Run:

```powershell
python .\connectors\sp500_constituents_daily_connector.py --start 2024-01-01 --end 2024-12-31 --output .\data\sp500_constituents_daily.csv
```

Output columns:

```text
ticker, yahoo_symbol, company, sector, date, open, high, low, close, volume, daily_return
```

This connector downloads the current S&P 500 constituent list, then downloads
daily OHLCV data for each constituent and calculates `daily_return` separately
within each ticker's time series. The first row for each ticker has a blank
`daily_return` because there is no prior close for that ticker in the downloaded
window. The current constituent list is read from the public Wikipedia
constituents table; use a licensed S&P/NYSE data source instead if you need an
official production feed.

For a quick smoke test, limit the number of constituents:

```powershell
python .\connectors\sp500_constituents_daily_connector.py --start 2024-01-02 --end 2024-01-05 --limit 3 --output .\data\sp500_constituents_daily_sample.csv
```

## Note on NYSE data

The S&P 500 is a market index, not a NYSE-listed stock, and its constituents
trade across multiple exchanges. NYSE's official historical data products are
licensed data feeds distributed through NYSE market data channels, not a simple
free public CSV endpoint. This connector therefore downloads daily S&P 500
index OHLCV data from a public chart endpoint while keeping the implementation
isolated so a licensed NYSE feed can be swapped in later.
