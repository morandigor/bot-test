"""Configuration module for the signal bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Application settings loaded from env."""

    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    dry_run: bool = os.getenv("DRY_RUN", "true").lower() in {"1", "true", "yes", "on"}
    send_test_message: bool = os.getenv("SEND_TEST_MESSAGE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    test_message_text: str = os.getenv(
        "TEST_MESSAGE_TEXT",
        "Teste Telegram OK - signal-bot",
    )

    timeframe_signal: str = os.getenv("TIMEFRAME_SIGNAL", "15min")
    timeframe_trend: str = os.getenv("TIMEFRAME_TREND", "1h")
    outputsize: int = int(os.getenv("OUTPUTSIZE", "500"))

    check_interval_seconds: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    max_signals_per_day: int = int(os.getenv("MAX_SIGNALS_PER_DAY", "3"))
    cooldown_hours_per_symbol: int = int(os.getenv("COOLDOWN_HOURS_PER_SYMBOL", "4"))
    duplicate_window_minutes: int = int(os.getenv("DUPLICATE_WINDOW_MINUTES", "360"))

    timezone: str = os.getenv("BOT_TIMEZONE", "UTC")
    state_file: str = os.getenv("STATE_FILE", "state.json")
    log_file: str = os.getenv("LOG_FILE", "logs/bot.log")

    signal_score_threshold: int = int(os.getenv("SIGNAL_SCORE_THRESHOLD", "5"))
    min_rr: float = float(os.getenv("MIN_RR", "2.0"))
    preferred_rr: float = float(os.getenv("PREFERRED_RR", "2.5"))


SYMBOL_CANDIDATES: Dict[str, List[str]] = {
    "XAU/USD": ["XAU/USD", "XAUUSD"],
    "USD/CHF": ["USD/CHF", "USDCHF"],
}

CONFIG = Config()
