"""Run a single scan cycle (useful for GitHub Actions and manual tests)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bot import run_once, setup_logging, validate_runtime_config
from config import CONFIG
from state import StateManager
from telegram import send_message
from twelve_data import TwelveDataClient


def main() -> None:
    """Execute one cycle and exit."""
    validate_runtime_config()
    logger = setup_logging(CONFIG.log_file)

    if CONFIG.send_test_message:
        timestamp = datetime.now(timezone.utc).isoformat()
        text = f"{CONFIG.test_message_text}\nTimestamp: {timestamp}"
        sent = send_message(
            bot_token=CONFIG.telegram_bot_token,
            chat_id=CONFIG.telegram_chat_id,
            message=text,
            dry_run=CONFIG.dry_run,
        )
        logger.info("telegram_test_message_sent=%s dry_run=%s", sent, CONFIG.dry_run)
        return

    state_manager = StateManager(Path(CONFIG.state_file))
    state = state_manager.load()
    client = TwelveDataClient()
    run_once(logger, client, state_manager, state)


if __name__ == "__main__":
    main()
