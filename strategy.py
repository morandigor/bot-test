"""Signal generation strategy with conservative multi-confirmation scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from indicators import atr, ema, macd, rsi
from risk import calculate_levels


@dataclass
class Signal:
    """Trading signal payload."""

    symbol: str
    direction: str
    entry: float
    sl: float
    tp: float
    rr: float
    timestamp: str
    score: int
    reason: str
    tp2: Optional[float] = None
    tp3: Optional[float] = None


def _is_bullish_rejection(prev_candle: pd.Series, last_candle: pd.Series) -> bool:
    body = abs(last_candle["close"] - last_candle["open"])
    lower_wick = min(last_candle["open"], last_candle["close"]) - last_candle["low"]
    bullish_pin = last_candle["close"] > last_candle["open"] and lower_wick > (1.2 * body)

    bullish_engulf = (
        prev_candle["close"] < prev_candle["open"]
        and last_candle["close"] > last_candle["open"]
        and last_candle["open"] <= prev_candle["close"]
        and last_candle["close"] >= prev_candle["open"]
    )
    return bool(bullish_pin or bullish_engulf)


def _is_bearish_rejection(prev_candle: pd.Series, last_candle: pd.Series) -> bool:
    body = abs(last_candle["close"] - last_candle["open"])
    upper_wick = last_candle["high"] - max(last_candle["open"], last_candle["close"])
    bearish_pin = last_candle["close"] < last_candle["open"] and upper_wick > (1.2 * body)

    bearish_engulf = (
        prev_candle["close"] > prev_candle["open"]
        and last_candle["close"] < last_candle["open"]
        and last_candle["open"] >= prev_candle["close"]
        and last_candle["close"] <= prev_candle["open"]
    )
    return bool(bearish_pin or bearish_engulf)


def _breakout_retest_buy(df: pd.DataFrame) -> bool:
    if len(df) < 25:
        return False
    broken_level = df["high"].iloc[-22:-2].max()
    broke = df["close"].iloc[-2] > broken_level
    retested = df["low"].iloc[-1] <= broken_level and df["close"].iloc[-1] > broken_level
    return bool(broke and retested)


def _breakout_retest_sell(df: pd.DataFrame) -> bool:
    if len(df) < 25:
        return False
    broken_level = df["low"].iloc[-22:-2].min()
    broke = df["close"].iloc[-2] < broken_level
    retested = df["high"].iloc[-1] >= broken_level and df["close"].iloc[-1] < broken_level
    return bool(broke and retested)


def generate_signal(
    symbol: str,
    df_15m: pd.DataFrame,
    df_1h: pd.DataFrame,
    score_threshold: int,
    min_rr: float,
    preferred_rr: float,
) -> Optional[Signal]:
    """Generate a high-conviction signal if all constraints are met."""
    if len(df_15m) < 220 or len(df_1h) < 220:
        return None

    data = df_15m.copy()
    data["ema50"] = ema(data["close"], 50)
    data["ema200"] = ema(data["close"], 200)
    data["rsi14"] = rsi(data["close"], 14)
    data["atr14"] = atr(data, 14)
    macd_df = macd(data["close"])
    data = pd.concat([data, macd_df], axis=1)

    trend_h1 = df_1h.copy()
    trend_h1["ema50"] = ema(trend_h1["close"], 50)
    trend_h1["ema200"] = ema(trend_h1["close"], 200)

    last = data.iloc[-1]
    prev = data.iloc[-2]

    # Volatility filter: avoid very compressed ATR relative to price.
    atr_ratio = float(last["atr14"] / last["close"])
    if atr_ratio < 0.0012:
        return None

    direction = "BUY" if last["ema50"] > last["ema200"] else "SELL"
    score = 0
    reasons = []
    confirmations = 0

    # Trend score
    if direction == "BUY":
        score += 2
        reasons.append("trend 15m (EMA50>EMA200)")
    else:
        score += 2
        reasons.append("trend 15m (EMA50<EMA200)")
    confirmations += 1

    h1_last = trend_h1.iloc[-1]
    h1_buy = h1_last["ema50"] > h1_last["ema200"]
    if (direction == "BUY" and h1_buy) or (direction == "SELL" and not h1_buy):
        score += 1
        reasons.append("trend 1h confirma")
        confirmations += 1

    # Momentum score
    momentum_ok = False
    if direction == "BUY":
        rsi_ok = last["rsi14"] > 55
        macd_ok = last["macd_hist"] > 0
        if rsi_ok:
            score += 1
            reasons.append("RSI14>55")
        if macd_ok:
            score += 1
            reasons.append("MACD hist positivo")
        momentum_ok = rsi_ok or macd_ok
    else:
        rsi_ok = last["rsi14"] < 45
        macd_ok = last["macd_hist"] < 0
        if rsi_ok:
            score += 1
            reasons.append("RSI14<45")
        if macd_ok:
            score += 1
            reasons.append("MACD hist negativo")
        momentum_ok = rsi_ok or macd_ok

    if momentum_ok:
        confirmations += 1

    # Structure score
    near_ema50 = abs(prev["close"] - prev["ema50"]) <= (0.35 * prev["atr14"])
    crossed_ema50 = prev["low"] <= prev["ema50"] <= prev["high"]

    pullback_ok = False
    breakout_retest_ok = False

    if direction == "BUY":
        pullback_ok = bool((near_ema50 or crossed_ema50) and _is_bullish_rejection(prev, last))
        breakout_retest_ok = _breakout_retest_buy(data)
    else:
        pullback_ok = bool((near_ema50 or crossed_ema50) and _is_bearish_rejection(prev, last))
        breakout_retest_ok = _breakout_retest_sell(data)

    if pullback_ok:
        score += 2
        reasons.append("pullback EMA50 + candle rejeição")
        confirmations += 1

    if breakout_retest_ok:
        score += 2
        reasons.append("rompimento + reteste")
        confirmations += 1

    if confirmations < 3 or score < score_threshold:
        return None

    # Entry: use EMA50 as conservative pullback entry when close enough, else last close.
    entry = float(last["close"])
    if pullback_ok and abs(last["close"] - last["ema50"]) <= (0.25 * last["atr14"]):
        entry = float(last["ema50"])

    levels = calculate_levels(
        direction=direction,
        entry=entry,
        atr_value=float(last["atr14"]),
        df=data,
        min_rr=min_rr,
        preferred_rr=preferred_rr,
    )
    if not levels:
        return None

    partials = levels.get("partials", [])
    tp2 = partials[0] if len(partials) > 0 else None
    tp3 = partials[1] if len(partials) > 1 else None

    reason = " + ".join(reasons)

    return Signal(
        symbol=symbol,
        direction=direction,
        entry=float(levels["entry"]),
        sl=float(levels["sl"]),
        tp=float(levels["tp"]),
        rr=float(levels["rr"]),
        tp2=float(tp2) if tp2 is not None else None,
        tp3=float(tp3) if tp3 is not None else None,
        timestamp=data.index[-1].isoformat(),
        score=score,
        reason=reason,
    )
