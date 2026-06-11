"""SQLite log všech signálů a jejich výsledků.

Jedna tabulka 'signals' = kompletní záznam: zpráva, analýza LLM, rozhodnutí,
vstupní cena a později doplněné ceny po 1h/4h/24h + výsledek obchodu.

Tohle je SEMÍNKO pro krok 2 (paměť/retrieval) a krok 3 (statistika/kalibrace).
Loguje se KAŽDÝ analyzovaný signál – i ten, co se neobchodoval – protože
z "co bych byl udělal" se učí stejně jako z reálných (paper) obchodů.
"""
from __future__ import annotations

import sqlite3
import time

from models import Analysis, NewsItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    news_id TEXT, title TEXT, url TEXT, source TEXT, currencies TEXT,
    triage_reason TEXT,
    analysis_json TEXT,
    direction TEXT, confidence REAL, magnitude TEXT, horizon TEXT,
    decision TEXT, side TEXT, size_value REAL, decision_reason TEXT,
    entry_price REAL,
    price_1h REAL, pnl_1h REAL,
    price_4h REAL, pnl_4h REAL,
    price_24h REAL, pnl_24h REAL,
    exit_price REAL, exit_reason TEXT, realized_pnl REAL, outcome_tag TEXT
);
"""


class Storage:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def log_signal(self, item: NewsItem, triage_reason: str,
                   analysis: Analysis, decision) -> int:
        cur = self.conn.execute(
            """INSERT INTO signals
               (ts, news_id, title, url, source, currencies, triage_reason,
                analysis_json, direction, confidence, magnitude, horizon,
                decision, side, size_value, decision_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (time.strftime("%Y-%m-%d %H:%M:%S"), item.id, item.title, item.url,
             item.source, ",".join(item.currencies), triage_reason,
             analysis.raw, analysis.direction, analysis.confidence,
             analysis.magnitude, analysis.horizon,
             decision.action, decision.side, decision.size_value, decision.reason),
        )
        self.conn.commit()
        return cur.lastrowid

    def set_entry(self, sid: int, price: float):
        self.conn.execute("UPDATE signals SET entry_price=? WHERE id=?", (price, sid))
        self.conn.commit()

    def set_outcome(self, sid: int, horizon: str, price: float, pnl: float):
        # horizon je vždy klíč z config.OUTCOME_HORIZONS ("1h"/"4h"/"24h") => bezpečné
        self.conn.execute(
            f"UPDATE signals SET price_{horizon}=?, pnl_{horizon}=? WHERE id=?",
            (price, pnl, sid))
        self.conn.commit()

    def set_exit(self, sid: int, price: float, reason: str, pnl: float, tag: str):
        self.conn.execute(
            "UPDATE signals SET exit_price=?, exit_reason=?, realized_pnl=?, "
            "outcome_tag=? WHERE id=?",
            (price, reason, pnl, tag, sid))
        self.conn.commit()

    def summary(self) -> dict:
        c = self.conn.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN decision='open' THEN 1 ELSE 0 END), "
            "SUM(COALESCE(realized_pnl, 0)) FROM signals")
        total, opened, pnl = c.fetchone()
        return {"signals": total or 0, "trades": opened or 0,
                "realized_pnl": pnl or 0.0}

    # --- KROK 2 (paměť): až bude log plný, sem přijde retrieval ---
    def find_similar_past_signals(self, item: NewsItem, limit: int = 5) -> list:
        """TODO: vrátit podobné minulé zprávy + jejich výsledky (embeddingy /
        vektorové hledání). Ty se pak vloží LLM do kontextu = učení ze
        zkušenosti bez trénování. Teď schválně prázdné – nejdřív nasbírat data.
        """
        return []

    # --- obnova stavu po restartu (aby se otevřené pozice neztratily/neduplikovaly) ---
    def get_open_positions(self) -> list:
        """Pozice otevřené v DB (decision='open', mají vstup, nemají exit)."""
        return self.conn.execute(
            "SELECT id, side, size_value, entry_price, currencies, ts, "
            "price_1h, price_4h, price_24h "
            "FROM signals WHERE decision='open' AND entry_price IS NOT NULL "
            "AND exit_price IS NULL"
        ).fetchall()

    def total_realized(self) -> float:
        """Součet realizovaného P/L ze všech uzavřených obchodů (pro obnovu po restartu)."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(realized_pnl), 0) FROM signals "
            "WHERE realized_pnl IS NOT NULL"
        ).fetchone()
        return float(row[0]) if row else 0.0

    def close(self):
        self.conn.close()
