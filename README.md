# Stock Analysis Connectors

This workspace contains a small connector for downloading daily S&P 500 index
price history as CSV.

## S&P 500 daily connector

Run:

```powershell
python .\connectors\sp500_daily_connector.py --start 2024-01-01 --end 2024-12-31 --output .\data\sp500_daily.csv
```

Output columns:

```text
date, open, high, low, close, volume
```

The default symbol is `^GSPC`, which represents the S&P 500 index. You can
override it with `--symbol` if your upstream data source uses a different code.

## Note on NYSE data

The S&P 500 is a market index, not a NYSE-listed stock, and its constituents
trade across multiple exchanges. NYSE's official historical data products are
licensed data feeds distributed through NYSE market data channels, not a simple
free public CSV endpoint. This connector therefore downloads daily S&P 500
index OHLCV data from a public chart endpoint while keeping the implementation
isolated so a licensed NYSE feed can be swapped in later.
