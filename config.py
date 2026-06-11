"""Konfigurace bota.

API klíče se čtou z proměnných prostředí (env variables) přes os.getenv.
- Na hostingu je nastav jako reálné env variables (systemd EnvironmentFile= /
  Environment=, nebo v UI platformy).
- Lokálně je pro pohodlí načte z .env souboru (python-dotenv), pokud existuje.
Klíče NIKDY nepatří do gitu.
"""
from __future__ import annotations

import os

# python-dotenv je volitelný – jen kvůli lokálnímu .env. Na hostingu s reálnými
# env variables není potřeba; kód čte z os.getenv tak jako tak.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- API klíče (z proměnných prostředí) ---
# Zprávy jdou z veřejných RSS feedů → žádný news klíč není potřeba (viz ingest.py).
LLM_API_KEY = os.getenv("LLM_API_KEY", "")                      # free, viz README

# --- Sledovaná aktiva (whitelist = zároveň likviditní pojistka) ---
# Obchoduje se POUZE to, co je tady. Drž se likvidních párů; sentiment
# i fill jsou u velkých coinů mnohem spolehlivější než u malých altů.
TRACKED_ASSETS: dict[str, str] = {
    # kód ve zprávách -> obchodní pár na burze (CCXT formát)
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "DOGE": "DOGE/USDT",
}

# --- Triage: klíčová slova, která zvyšují relevanci (volitelný signál) ---
MOVING_KEYWORDS = [
    "hack", "exploit", "lawsuit", "sec", "ban", "etf", "listing",
    "delisting", "partnership", "upgrade", "fork", "halving",
    "approval", "approved", "rejected", "outage", "depeg", "liquidation",
]

# --- LLM (OpenAI-kompatibilní – funguje i ZADARMO) ---
# Výchozí: Groq free tier – rychlý, bez platební karty. Free klíč dej do .env
# jako LLM_API_KEY (https://console.groq.com/keys).
# Jiný poskytovatel = jen změň base_url + model:
#   Gemini (free):  https://generativelanguage.googleapis.com/v1beta/openai/   model "gemini-2.5-flash"
#   Ollama (offline, bez klíče): http://localhost:11434/v1                      model "llama3.1"
#   OpenAI/jiné (placené):       https://api.openai.com/v1                       model "gpt-4o-mini"
LLM_BASE_URL = "https://api.groq.com/openai/v1"
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_MAX_TOKENS = 600

# --- Riziko / paper portfolio ---
STARTING_CAPITAL = 10_000.0     # virtuální kapitál (quote měna, USDT)
MIN_CONFIDENCE = 0.65           # pod tímto prahem jistoty se NEobchoduje
POSITION_FRACTION = 0.05        # 5 % kapitálu na jeden obchod
MAX_POSITION_VALUE = 1_000.0    # tvrdý strop na jednu pozici (USDT)
MAX_OPEN_POSITIONS = 5
DAILY_LOSS_LIMIT = 500.0        # kill switch: max denní ztráta (USDT)
STOP_LOSS_PCT = 0.05            # -5 % stop-loss
TAKE_PROFIT_PCT = 0.10          # +10 % take-profit
MAX_HOLD_SECONDS = 24 * 3600    # po 24 h pozici zavři tak jako tak

# --- Sledování výsledku signálu (labely pro pozdější učení) ---
OUTCOME_HORIZONS = {            # název sloupce -> sekundy po vstupu
    "1h": 1 * 3600,
    "4h": 4 * 3600,
    "24h": 24 * 3600,
}

# --- Běh ---
PRICE_EXCHANGE = "kraken"       # CCXT burza pro CENY (public data, bez klíče)
POLL_INTERVAL_SECONDS = 60      # jak často tahat nové zprávy
TICK_INTERVAL_SECONDS = 30      # jak často přepočítávat pozice / outcomy
HEARTBEAT_SECONDS = 600         # jak často vypsat "žiju" status
MAX_RUNTIME_SECONDS = 7 * 24 * 3600   # auto-stop po týdnu (None = běž napořád)
DB_PATH = os.getenv("DB_PATH", "trading_log.db")  # na hostingu nasměruj na persistent volume
