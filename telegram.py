"""Telegram message sender with dry-run support."""

from __future__ import annotations

import json
from typing import Optional

import requests


def send_message(
    bot_token: str,
    chat_id: str,
    message: str,
    dry_run: bool = True,
    timeout: int = 15,
) -> bool:
    """Send message to Telegram or print when dry-run is enabled."""
    if dry_run:
        print("[DRY-RUN] Telegram message:")
        print(message)
        return True

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return bool(data.get("ok", False))
    except requests.RequestException as exc:
        print(f"Telegram send failed: {exc}")
        return False
    except json.JSONDecodeError:
        print("Telegram send failed: invalid JSON response")
        return False
