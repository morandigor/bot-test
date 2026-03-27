"""Market data helpers backed by yfinance.

The module name and client class are kept for compatibility with the rest of the
project, but the underlying provider is yfinance.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import yfinance as yf

SYMBOL_MAP = {
    "XAU/USD": "GC=F",
    "XAUUSD": "GC=F",
    "USD/CHF": "USDCHF=X",
    "USDCHF": "USDCHF=X",
}

INTERVAL_MAP = {
    "1min": ("1m", "7d"),
    "5min": ("5m", "60d"),
    "15min": ("15m", "60d"),
    "30min": ("30m", "60d"),
    "45min": ("60m", "60d"),
    "1h": ("60m", "730d"),
    "4h": ("1h", "730d"),
    "1day": ("1d", "max"),
}


class TwelveDataError(Exception):
    """Raised when market data fetch or normalization fails."""


class TwelveDataClient:
    """Compatibility wrapper exposing the same client-style interface."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int = 15) -> None:
        del base_url, api_key, timeout

    @staticmethod
    def _map_symbol(symbol: str) -> str:
        return SYMBOL_MAP.get(symbol, symbol)

    @staticmethod
    def _map_interval(interval: str) -> tuple[str, str]:
        if interval not in INTERVAL_MAP:
            raise TwelveDataError(f"Unsupported timeframe: {interval}")
        return INTERVAL_MAP[interval]

    @staticmethod
    def _normalize_history(df: pd.DataFrame, outputsize: int) -> pd.DataFrame:
        if df.empty:
            raise TwelveDataError("No time series data returned")

        normalized = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        ).copy()

        if "volume" not in normalized.columns:
            normalized["volume"] = 0.0

        normalized.index = pd.to_datetime(normalized.index, utc=True, errors="coerce")
        normalized = normalized[["open", "high", "low", "close", "volume"]]
        normalized = normalized.apply(pd.to_numeric, errors="coerce")
        normalized = normalized.dropna(subset=["open", "high", "low", "close"])
        normalized = normalized[~normalized.index.isna()]
        normalized = normalized.sort_index()

        if outputsize > 0:
            normalized = normalized.tail(outputsize)

        if normalized.empty:
            raise TwelveDataError("No normalized candle data available")

        return normalized

    def get_time_series(self, symbol: str, interval: str, outputsize: int = 500) -> pd.DataFrame:
        """Fetch OHLCV as a normalized DataFrame indexed by datetime."""
        ticker = self._map_symbol(symbol)
        yf_interval, period = self._map_interval(interval)

        try:
            history = yf.Ticker(ticker).history(interval=yf_interval, period=period, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001
            raise TwelveDataError(f"Failed to fetch time series for {symbol} {interval}: {exc}") from exc

        return self._normalize_history(history, outputsize)

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch the latest traded price for the symbol."""
        candles = self.get_time_series(symbol, "1min", outputsize=1)
        last_close = candles["close"].iloc[-1]
        return {"symbol": symbol, "price": float(last_close)}

    def get_candles(self, symbol: str, timeframe: str, outputsize: int = 500) -> pd.DataFrame:
        """Compatibility alias requested by the project contract."""
        return self.get_time_series(symbol, timeframe, outputsize)

    def get_price(self, symbol: str) -> float:
        """Compatibility alias requested by the project contract."""
        return float(self.get_quote(symbol)["price"])
