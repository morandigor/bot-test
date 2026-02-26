"""Twelve Data API client helpers with retries and normalization."""

from __future__ import annotations

import time
from typing import Any, Dict

import pandas as pd
import requests


class TwelveDataError(Exception):
    """Raised when Twelve Data request fails after retries."""


class TwelveDataClient:
    """Small REST client for Twelve Data endpoints used by the bot."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request_with_retry(
        self,
        endpoint: str,
        params: Dict[str, Any],
        max_retries: int = 5,
        backoff_base: float = 1.0,
    ) -> Dict[str, Any]:
        """Call Twelve Data endpoint with exponential backoff retry."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        merged = {**params, "apikey": self.api_key}

        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=merged, timeout=self.timeout)
                if response.status_code == 429:
                    raise TwelveDataError("Rate limit (429)")
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "error":
                    code = data.get("code")
                    message = data.get("message", "Unknown API error")
                    if code in {429, 500, 503}:
                        raise TwelveDataError(f"Transient API error: {code} - {message}")
                    raise TwelveDataError(f"API error: {code} - {message}")

                return data

            except (requests.RequestException, TwelveDataError) as exc:
                is_last = attempt >= max_retries - 1
                if is_last:
                    raise TwelveDataError(
                        f"Request failed after {max_retries} attempts: {exc}"
                    ) from exc

                sleep_s = backoff_base * (2 ** attempt)
                time.sleep(sleep_s)

        raise TwelveDataError("Unexpected retry loop termination")

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch last quote for symbol."""
        return self._request_with_retry("quote", {"symbol": symbol})

    def get_time_series(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 500,
    ) -> pd.DataFrame:
        """Fetch OHLCV as normalized DataFrame indexed by datetime (ascending)."""
        raw = self._request_with_retry(
            "time_series",
            {
                "symbol": symbol,
                "interval": interval,
                "outputsize": outputsize,
                "format": "JSON",
            },
        )

        values = raw.get("values")
        if not values:
            raise TwelveDataError(f"No time series data returned for {symbol} {interval}")

        df = pd.DataFrame(values)
        required = ["datetime", "open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise TwelveDataError(f"Missing columns in response: {missing}")

        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["datetime", "open", "high", "low", "close"]).copy()
        df = df.set_index("datetime").sort_index()

        return df
