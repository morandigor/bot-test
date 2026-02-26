"""Main loop for the conservative signal bot (no order execution)."""

from __future__ import annotations

import json
import logging
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from config import CONFIG, SYMBOL_CANDIDATES
from state import StateManager
from strategy import Signal, generate_signal
from telegram import send_message
from twelve_data import TwelveDataClient, TwelveDataError

RUNNING = True


def setup_logging(log_file: str) -> logging.Logger:
    """Configure logger to write structured lines to file and console."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("signal_bot")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def signal_handler(signum: int, frame: object) -> None:
    """Gracefully stop bot loop on Ctrl+C or TERM."""
    del signum, frame
    global RUNNING
    RUNNING = False


def now_in_tz(tz_name: str) -> datetime:
    """Return timezone-aware now."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def resolve_symbol_data(
    client: TwelveDataClient,
    canonical_symbol: str,
    interval_signal: str,
    interval_trend: str,
    outputsize: int,
) -> Optional[Tuple[str, object, object]]:
    """Try symbol candidates and return first valid data pair."""
    for candidate in SYMBOL_CANDIDATES.get(canonical_symbol, [canonical_symbol]):
        try:
            df_15 = client.get_time_series(candidate, interval_signal, outputsize)
            df_1h = client.get_time_series(candidate, interval_trend, outputsize)
            return candidate, df_15, df_1h
        except TwelveDataError:
            continue
    return None


def format_signal_message(sig: Signal) -> str:
    """Build Telegram message with required fields."""
    lines = [
        "[HIGH-CONVICTION SIGNAL]",
        f"Ativo: {sig.symbol}",
        f"Direção: {sig.direction}",
        f"Entry: {sig.entry}",
        f"SL: {sig.sl}",
        f"TP: {sig.tp}",
    ]

    if sig.tp2 is not None:
        lines.append(f"TP2: {sig.tp2}")
    if sig.tp3 is not None:
        lines.append(f"TP3: {sig.tp3}")

    lines.extend(
        [
            f"R:R estimado: {sig.rr}",
            f"Score de convicção: {sig.score}",
            f"Timestamp: {sig.timestamp}",
            f"Justificativa: {sig.reason}",
            "Aviso: sinal educacional, sem garantia de resultado.",
        ]
    )
    return "\n".join(lines)


def log_event(logger: logging.Logger, event: str, **data: object) -> None:
    """Emit structured log payload."""
    payload = {"event": event, **data}
    logger.info(json.dumps(payload, default=str))


def run_once(
    logger: logging.Logger,
    client: TwelveDataClient,
    state_manager: StateManager,
    state: dict,
) -> None:
    """One full scan cycle across all symbols."""
    now = now_in_tz(CONFIG.timezone)
    date_key = now.date().isoformat()
    state_manager.reset_daily_if_needed(state, date_key)

    if int(state["daily_count"].get("count", 0)) >= CONFIG.max_signals_per_day:
        log_event(logger, "daily_cap_reached", count=state["daily_count"].get("count", 0))
        return

    for canonical_symbol in SYMBOL_CANDIDATES.keys():
        if int(state["daily_count"].get("count", 0)) >= CONFIG.max_signals_per_day:
            break

        data = resolve_symbol_data(
            client=client,
            canonical_symbol=canonical_symbol,
            interval_signal=CONFIG.timeframe_signal,
            interval_trend=CONFIG.timeframe_trend,
            outputsize=CONFIG.outputsize,
        )
        if not data:
            log_event(logger, "data_fetch_failed", symbol=canonical_symbol)
            continue

        used_symbol, df_15, df_1h = data

        sig = generate_signal(
            symbol=canonical_symbol,
            df_15m=df_15,
            df_1h=df_1h,
            score_threshold=CONFIG.signal_score_threshold,
            min_rr=CONFIG.min_rr,
            preferred_rr=CONFIG.preferred_rr,
        )

        if not sig:
            log_event(logger, "no_setup", symbol=canonical_symbol, used_symbol=used_symbol)
            continue

        allowed = state_manager.can_send_signal(
            state=state,
            symbol=canonical_symbol,
            direction=sig.direction,
            now=now,
            max_signals_per_day=CONFIG.max_signals_per_day,
            cooldown_hours=CONFIG.cooldown_hours_per_symbol,
            duplicate_window_minutes=CONFIG.duplicate_window_minutes,
        )
        if not allowed:
            log_event(
                logger,
                "blocked_by_limits",
                symbol=canonical_symbol,
                direction=sig.direction,
            )
            continue

        text = format_signal_message(sig)
        sent = send_message(
            bot_token=CONFIG.telegram_bot_token,
            chat_id=CONFIG.telegram_chat_id,
            message=text,
            dry_run=CONFIG.dry_run,
        )

        log_event(
            logger,
            "signal_sent" if sent else "signal_send_failed",
            symbol=canonical_symbol,
            direction=sig.direction,
            score=sig.score,
            rr=sig.rr,
            dry_run=CONFIG.dry_run,
        )

        if sent:
            state_manager.register_signal(
                state=state,
                symbol=canonical_symbol,
                direction=sig.direction,
                now=now,
            )
            state_manager.save(state)


def validate_runtime_config() -> None:
    """Validate required credentials."""
    if not CONFIG.twelve_data_api_key:
        raise ValueError("TWELVE_DATA_API_KEY ausente. Configure no .env.")
    if not CONFIG.dry_run and (not CONFIG.telegram_bot_token or not CONFIG.telegram_chat_id):
        raise ValueError(
            "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes. Configure no .env para envio real."
        )


def main() -> None:
    """Entrypoint for bot process."""
    logger = setup_logging(CONFIG.log_file)

    validate_runtime_config()

    state_manager = StateManager(Path(CONFIG.state_file))
    state = state_manager.load()

    client = TwelveDataClient(
        base_url=CONFIG.base_url_twelve,
        api_key=CONFIG.twelve_data_api_key,
    )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log_event(
        logger,
        "bot_started",
        dry_run=CONFIG.dry_run,
        timeframe_signal=CONFIG.timeframe_signal,
        timeframe_trend=CONFIG.timeframe_trend,
        check_interval_seconds=CONFIG.check_interval_seconds,
        max_signals_per_day=CONFIG.max_signals_per_day,
    )

    while RUNNING:
        cycle_start = time.time()
        try:
            run_once(logger, client, state_manager, state)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "cycle_exception", error=str(exc))

        elapsed = time.time() - cycle_start
        sleep_s = max(1, CONFIG.check_interval_seconds - int(elapsed))
        for _ in range(sleep_s):
            if not RUNNING:
                break
            time.sleep(1)

    log_event(logger, "bot_stopped")


if __name__ == "__main__":
    main()
