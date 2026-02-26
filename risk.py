"""Risk, SL/TP and RR calculations."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


class RiskError(Exception):
    """Raised when risk parameters are invalid."""


def _round_price(value: float) -> float:
    return round(float(value), 5)


def calculate_levels(
    direction: str,
    entry: float,
    atr_value: float,
    df: pd.DataFrame,
    min_rr: float,
    preferred_rr: float,
) -> Optional[Dict[str, object]]:
    """Compute SL/TP levels and validate minimum RR.

    SL uses ATR and recent swing.
    TP target aims for preferred RR first; falls back to minimum RR.
    """
    if atr_value <= 0:
        raise RiskError("ATR must be > 0")

    recent = df.tail(30)
    swing_low = float(recent["low"].min())
    swing_high = float(recent["high"].max())

    if direction == "BUY":
        sl_atr = entry - (1.5 * atr_value)
        sl_swing = swing_low - (0.2 * atr_value)
        sl = min(sl_atr, sl_swing)
        risk = entry - sl
        if risk <= 0:
            return None

        projected_target = swing_high + atr_value
        max_rr = (projected_target - entry) / risk
        if max_rr < min_rr:
            return None

        rr_primary = preferred_rr if max_rr >= preferred_rr else min_rr
        tp = entry + rr_primary * risk
        tp2 = entry + 3.0 * risk if max_rr >= 3.0 else None
        tp3 = entry + 3.5 * risk if max_rr >= 3.5 else None

    elif direction == "SELL":
        sl_atr = entry + (1.5 * atr_value)
        sl_swing = swing_high + (0.2 * atr_value)
        sl = max(sl_atr, sl_swing)
        risk = sl - entry
        if risk <= 0:
            return None

        projected_target = swing_low - atr_value
        max_rr = (entry - projected_target) / risk
        if max_rr < min_rr:
            return None

        rr_primary = preferred_rr if max_rr >= preferred_rr else min_rr
        tp = entry - rr_primary * risk
        tp2 = entry - 3.0 * risk if max_rr >= 3.0 else None
        tp3 = entry - 3.5 * risk if max_rr >= 3.5 else None

    else:
        raise RiskError(f"Invalid direction: {direction}")

    levels: Dict[str, object] = {
        "entry": _round_price(entry),
        "sl": _round_price(sl),
        "tp": _round_price(tp),
        "rr": round(rr_primary, 2),
    }

    partials: List[float] = []
    if tp2 is not None:
        partials.append(_round_price(tp2))
    if tp3 is not None:
        partials.append(_round_price(tp3))
    if partials:
        levels["partials"] = partials

    return levels
