# Signal Bot (XAU/USD e USD/CHF)

Bot de sinais em Python para **XAU/USD** e **USD/CHF**.

- Nao executa ordens.
- Busca dados via Twelve Data (REST).
- Envia sinais no Telegram (ou simula em dry-run).
- Usa abordagem conservadora com confirmacoes tecnicas rastreaveis.

## Regras principais

- Timeframe base do sinal: `15min`
- Confirmacao de tendencia adicional: `1h`
- Checagem: a cada 5 minutos
- Limite diario: maximo de 3 sinais/dia (somando os dois ativos)
- Cooldown por ativo: 4 horas (configuravel)
- Bloqueio de repeticao de direcao recente (BUY->BUY)
- Score minimo de conviccao: `>= 5`
- RR minimo: `>= 2.0` (preferencia por `2.5`)

## Metodo de conviccao

Um sinal so e gerado quando ha confirmacoes suficientes:

1. Tendencia
- EMA(50) vs EMA(200) no 15m
- Confirmacao adicional no 1h

2. Momento
- RSI(14)
- MACD histograma

3. Volatilidade
- ATR(14) como filtro e para SL/TP

4. Estrutura
- Pullback na EMA50 + candle de rejeicao (pinbar/engolfo simplificado), ou
- Rompimento + reteste

## Estrutura de arquivos

- `requirements.txt`
- `config.py`
- `twelve_data.py`
- `indicators.py`
- `strategy.py`
- `risk.py`
- `telegram.py`
- `state.py`
- `bot.py`
- `bot_once.py`
- `app.py`
- `.github/workflows/signal_bot.yml`
- `README.md`

## Instalacao e execucao

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### Rodar dashboard Streamlit

```bash
streamlit run app.py
```

## Configuracao

O bot le variaveis de `.env`. Nao mantenha credenciais sensiveis hardcoded no codigo.

### Exemplo de `.env`

```env
TWELVE_DATA_API_KEY=coloque_sua_chave
TELEGRAM_CHAT_ID=seu_chat_id
TELEGRAM_BOT_TOKEN=seu_bot_token

DRY_RUN=true
TIMEFRAME_SIGNAL=15min
TIMEFRAME_TREND=1h
CHECK_INTERVAL_SECONDS=300
MAX_SIGNALS_PER_DAY=3
COOLDOWN_HOURS_PER_SYMBOL=4
DUPLICATE_WINDOW_MINUTES=360
BOT_TIMEZONE=UTC
STATE_FILE=state.json
LOG_FILE=logs/bot.log
SIGNAL_SCORE_THRESHOLD=5
MIN_RR=2.0
PREFERRED_RR=2.5
```

## Dry-run vs envio real

- `DRY_RUN=true`: nao envia no Telegram, apenas imprime no console.
- `DRY_RUN=false`: envia mensagem real via Telegram API.

## GitHub Actions (24/7 scheduler)

Workflow pronto em `.github/workflows/signal_bot.yml`:

- Agenda: a cada 5 minutos (`*/5 * * * *`)
- Executa `python bot_once.py` (um ciclo por run)
- Restaura e salva `state.json` e `logs/` via cache para manter cooldown/contador

Configure no repositório (Settings -> Secrets and variables -> Actions):

- `TWELVE_DATA_API_KEY`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_BOT_TOKEN`
- `DRY_RUN` (`true` ou `false`)

## Streamlit Cloud

Para publicar o painel:

1. Suba este projeto no GitHub.
2. No Streamlit Cloud, conecte o repo e selecione `app.py`.
3. Em Secrets do Streamlit, configure as mesmas variaveis do `.env`.

Observacao: Streamlit e painel/monitoramento. O agendamento 24/7 fica no GitHub Actions.

## Estado e logs

- Estado persistido em `state.json`:
  - contador diario por data
  - ultimos sinais por ativo
  - timestamp/direcao para cooldown e anti-duplicacao
- Logs estruturados em `logs/bot.log`

## Formato do sinal

Cada mensagem inclui:

- Ativo
- Direcao (BUY/SELL)
- Entry
- SL
- TP (e TP2/TP3 quando disponivel)
- R:R estimado
- Timestamp
- Justificativa curta baseada nas confirmacoes

## Avisos importantes

- Este projeto e educacional e nao promete lucro.
- Mercado envolve risco; valide qualquer sinal antes de operar.
- Em producao, rotacione credenciais periodicamente e mantenha `.env` fora do Git.
