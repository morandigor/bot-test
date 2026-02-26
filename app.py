"""Streamlit dashboard for monitoring the signal bot."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from bot_once import main as run_cycle_once
from config import CONFIG, SYMBOL_CANDIDATES
from state import StateManager

st.set_page_config(page_title="FX Signal Bot", layout="wide")
st.title("FX Signal Bot Dashboard")
st.caption("XAU/USD + USD/CHF | Sinais conservadores | Sem execução de ordens")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Timeframe Sinal", CONFIG.timeframe_signal)
col2.metric("Timeframe Tendência", CONFIG.timeframe_trend)
col3.metric("Limite Diário", str(CONFIG.max_signals_per_day))
col4.metric("Modo", "DRY-RUN" if CONFIG.dry_run else "REAL")

st.subheader("Configuração")
st.write(
    {
        "symbols": list(SYMBOL_CANDIDATES.keys()),
        "cooldown_hours_per_symbol": CONFIG.cooldown_hours_per_symbol,
        "duplicate_window_minutes": CONFIG.duplicate_window_minutes,
        "signal_score_threshold": CONFIG.signal_score_threshold,
        "min_rr": CONFIG.min_rr,
        "preferred_rr": CONFIG.preferred_rr,
        "check_interval_seconds": CONFIG.check_interval_seconds,
    }
)

st.subheader("Estado")
state_manager = StateManager(Path(CONFIG.state_file))
state = state_manager.load()
st.json(state)

st.subheader("Ações")
if st.button("Executar 1 ciclo agora"):
    try:
        run_cycle_once()
        st.success("Ciclo executado com sucesso.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao executar ciclo: {exc}")

st.subheader("Logs recentes")
log_path = Path(CONFIG.log_file)
if log_path.exists():
    lines = log_path.read_text(encoding="utf-8").splitlines()[-80:]
    parsed = []
    for line in lines:
        msg = line
        if "{" in line:
            try:
                msg = json.dumps(json.loads(line[line.index("{"):]), ensure_ascii=False)
            except Exception:
                pass
        parsed.append(msg)
    st.code("\n".join(parsed), language="text")
else:
    st.info("Arquivo de log ainda não existe.")
