"""Live stock index fetcher for JP/TW/US markets.

This script polls Yahoo Finance's public quote API every second to display
the latest index levels for:
- Japan Nikkei 225 (^N225)
- Taiwan TAIEX (^TWII)
- US S&P 500 (^GSPC)
- US Dow Jones Industrial Average (^DJI)
- US NASDAQ Composite (^IXIC)

Run the script directly with Python to start the ticker.
"""
from __future__ import annotations

import datetime as dt
import time
import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import requests

# Yahoo Finance symbol mapping for the requested indices.
DEFAULT_TICKERS: Dict[str, str] = {
    "Nikkei 225": "^N225",
    "TAIEX": "^TWII",
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "NASDAQ": "^IXIC",
}

API_URL = "https://query1.finance.yahoo.com/v7/finance/quote"


@dataclass
class Quote:
    """Container for a quote result."""

    name: str
    price: float
    change: float
    change_percent: float
    currency: str

    @classmethod
    def from_yahoo(cls, name: str, payload: Dict) -> "Quote":
        return cls(
            name=name,
            price=payload.get("regularMarketPrice", float("nan")),
            change=payload.get("regularMarketChange", float("nan")),
            change_percent=payload.get("regularMarketChangePercent", float("nan")),
            currency=payload.get("currency", ""),
        )


class YahooFinanceClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "stock-indices-live/1.0"})

    def fetch(self, tickers: Iterable[str]) -> Dict[str, Quote]:
        symbols = ",".join(tickers)
        response = self._session.get(API_URL, params={"symbols": symbols}, timeout=10)
        response.raise_for_status()
        data = response.json()
        result: List[Dict] = data.get("quoteResponse", {}).get("result", [])

        quotes: Dict[str, Quote] = {}
        for item in result:
            symbol = item.get("symbol", "")
            if not symbol:
                continue
            quotes[symbol] = Quote.from_yahoo(symbol, item)
        return quotes


def format_quote(name: str, quote: Quote | None) -> str:
    if quote is None:
        return f"{name:12}: (no data)"
    sign = "+" if quote.change > 0 else ""
    return (
        f"{name:12}: {quote.price:>10.2f} {quote.currency:<4}"
        f"  ({sign}{quote.change:.2f}, {sign}{quote.change_percent:.2f}%)"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll Yahoo Finance for live index quotes every second by default.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Refresh interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--indices",
        nargs="*",
        metavar="NAME=SYMBOL",
        help=(
            "Override default indices with NAME=SYMBOL pairs (e.g. 'Nikkei=^N225'). "
            "If omitted, built-in Nikkei/TAIEX/S&P/Dow/NASDAQ are used."
        ),
    )
    return parser.parse_args(argv)


def validate_interval(interval: float) -> float:
    if interval <= 0:
        raise ValueError("Interval must be greater than 0 seconds.")
    return interval


def parse_custom_indices(pairs: Sequence[str] | None) -> Dict[str, str]:
    if not pairs:
        return dict(DEFAULT_TICKERS)

    indices: Dict[str, str] = {}
    for raw in pairs:
        if "=" not in raw:
            raise ValueError(f"Invalid index spec '{raw}'. Use NAME=SYMBOL format.")
        name, symbol = raw.split("=", 1)
        name, symbol = name.strip(), symbol.strip()
        if not name or not symbol:
            raise ValueError(f"Invalid index spec '{raw}'. Name and symbol are required.")
        indices[name] = symbol
    return indices


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        interval = validate_interval(args.interval)
        tickers = parse_custom_indices(args.indices)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    client = YahooFinanceClient()
    symbols = list(tickers.values())

    try:
        while True:
            try:
                fetched = client.fetch(symbols)
            except requests.RequestException as exc:
                print(
                    f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] Error fetching quotes: {exc}"
                )
                time.sleep(interval)
                continue

            print(f"\n[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] Current indices")
            for name, symbol in tickers.items():
                quote = fetched.get(symbol)
                print(format_quote(name, quote))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
