"""Run a single scan cycle (useful for GitHub Actions and manual tests)."""

from __future__ import annotations

from pathlib import Path

from bot import run_once, setup_logging, validate_runtime_config
from config import CONFIG
from state import StateManager
from twelve_data import TwelveDataClient


def main() -> None:
    """Execute one cycle and exit."""
    validate_runtime_config()
    logger = setup_logging(CONFIG.log_file)
    state_manager = StateManager(Path(CONFIG.state_file))
    state = state_manager.load()
    client = TwelveDataClient()
    run_once(logger, client, state_manager, state)


if __name__ == "__main__":
    main()
