"""Persistent state manager for cooldown and daily limits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


@dataclass
class StateManager:
    """Load and persist bot state in JSON format."""

    path: Path

    def load(self) -> Dict[str, Any]:
        """Load state from disk or return defaults."""
        if not self.path.exists():
            return self._default_state()

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            merged = self._default_state()
            merged.update(data)
            merged.setdefault("daily_count", {})
            merged.setdefault("last_signals", {})
            return merged
        except (json.JSONDecodeError, OSError):
            return self._default_state()

    def save(self, state: Dict[str, Any]) -> None:
        """Persist state atomically-ish."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def reset_daily_if_needed(self, state: Dict[str, Any], date_key: str) -> None:
        """Reset daily counter if date changes."""
        daily = state.get("daily_count", {})
        if daily.get("date") != date_key:
            state["daily_count"] = {"date": date_key, "count": 0}

    def can_send_signal(
        self,
        state: Dict[str, Any],
        symbol: str,
        direction: str,
        now: datetime,
        max_signals_per_day: int,
        cooldown_hours: int,
        duplicate_window_minutes: int,
    ) -> bool:
        """Validate global daily cap, per-symbol cooldown and duplicate direction blocking."""
        daily = state.get("daily_count", {})
        if int(daily.get("count", 0)) >= max_signals_per_day:
            return False

        symbol_data = state.get("last_signals", {}).get(symbol)
        if not symbol_data:
            return True

        last_ts_raw = symbol_data.get("timestamp")
        if not last_ts_raw:
            return True

        try:
            last_ts = datetime.fromisoformat(last_ts_raw)
        except ValueError:
            return True

        if now - last_ts < timedelta(hours=cooldown_hours):
            return False

        same_direction_recent = (
            symbol_data.get("direction") == direction
            and now - last_ts < timedelta(minutes=duplicate_window_minutes)
        )
        if same_direction_recent:
            return False

        return True

    def register_signal(
        self,
        state: Dict[str, Any],
        symbol: str,
        direction: str,
        now: datetime,
    ) -> None:
        """Update state after sending signal."""
        state.setdefault("daily_count", {}).setdefault("count", 0)
        state["daily_count"]["count"] = int(state["daily_count"]["count"]) + 1

        state.setdefault("last_signals", {})
        state["last_signals"][symbol] = {
            "direction": direction,
            "timestamp": now.isoformat(),
        }

    @staticmethod
    def _default_state() -> Dict[str, Any]:
        return {
            "daily_count": {"date": "", "count": 0},
            "last_signals": {},
        }
