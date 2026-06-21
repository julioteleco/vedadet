"""Download historical data for ETFs from Yahoo Finance via yfinance.

Usage:
    python tools/download_etfs.py                       # SPY and QQQ, last 1 month
    python tools/download_etfs.py SPY QQQ VOO --period 1y --interval 1d
    python tools/download_etfs.py SPY QQQ --out data/etfs.csv

Note:
    This script needs outbound network access to Yahoo Finance hosts:
        query1.finance.yahoo.com
        query2.finance.yahoo.com
    In sandboxed/remote environments these must be added to the network
    egress allowlist, otherwise downloads fail with HTTP 403.
"""

import argparse
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Download ETF data from yfinance")
    parser.add_argument(
        "tickers",
        nargs="*",
        default=["SPY", "QQQ"],
        help="ETF tickers to download (default: SPY QQQ)",
    )
    parser.add_argument("--period", default="1mo", help="Period, e.g. 5d, 1mo, 1y, max")
    parser.add_argument("--interval", default="1d", help="Interval, e.g. 1d, 1h, 1wk")
    parser.add_argument("--out", default=None, help="Optional CSV output path")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance is not installed. Run: pip install yfinance")

    print(f"Downloading {args.tickers} (period={args.period}, interval={args.interval})...")
    data = yf.download(
        args.tickers,
        period=args.period,
        interval=args.interval,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    if data.empty:
        sys.exit(
            "No data returned. Likely the Yahoo Finance hosts are blocked by the "
            "network egress allowlist (HTTP 403). Allow query1/query2.finance.yahoo.com "
            "and retry."
        )

    print(f"Downloaded shape: {data.shape}")
    print(data.tail())

    if args.out:
        data.to_csv(args.out)
        print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
