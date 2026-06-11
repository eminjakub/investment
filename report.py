"""Samostatný report výdělku – spustíš kdykoli: `python report.py`.

Ukáže, kolik bot "vydělal": vložený (virtuální) kapitál, aktuální hodnotu,
zisk/ztrátu absolutně i v %, rozpad na realizovaný (uzavřené obchody) a
nerealizovaný (otevřené pozice oceněné aktuální cenou) a statistiku obchodů.

Funguje i ZA BĚHU bota – čte stejnou DB. Otevřené pozice oceňuje přes CCXT.
"""
from __future__ import annotations

import sqlite3

import ccxt

import config


def build_report(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # uzavřené obchody (mají realized_pnl)
    closed = conn.execute(
        "SELECT realized_pnl FROM signals WHERE realized_pnl IS NOT NULL"
    ).fetchall()
    realized_pnls = [r["realized_pnl"] for r in closed]
    realized = sum(realized_pnls)
    wins = [p for p in realized_pnls if p > 0]
    losses = [p for p in realized_pnls if p <= 0]

    # otevřené pozice: rozhodnutí 'open', máme vstup, ještě nezavřené
    open_rows = conn.execute(
        "SELECT side, size_value, entry_price, currencies, title "
        "FROM signals WHERE decision='open' AND entry_price IS NOT NULL "
        "AND exit_price IS NULL"
    ).fetchall()
    conn.close()

    exchange = getattr(ccxt, config.PRICE_EXCHANGE)()
    open_positions = []
    unrealized = 0.0
    for r in open_rows:
        codes = (r["currencies"] or "").split(",")
        symbol = next((config.TRACKED_ASSETS[c] for c in codes
                       if c in config.TRACKED_ASSETS), None)
        price = None
        if symbol:
            try:
                price = float(exchange.fetch_ticker(symbol)["last"])
            except Exception:
                price = None
        entry = r["entry_price"]
        qty = (r["size_value"] / entry) if entry else 0.0
        if price is not None:
            pnl = (price - entry) * qty if r["side"] == "long" else (entry - price) * qty
        else:
            pnl = 0.0
        unrealized += pnl
        open_positions.append({
            "symbol": symbol or "?", "side": r["side"], "entry": entry,
            "price": price, "pnl": pnl,
        })

    start = config.STARTING_CAPITAL
    equity = start + realized + unrealized
    return {
        "start": start,
        "equity": equity,
        "profit": equity - start,
        "return_pct": (equity - start) / start * 100 if start else 0.0,
        "realized": realized,
        "unrealized": unrealized,
        "n_trades": len(realized_pnls),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate": (len(wins) / len(realized_pnls) * 100) if realized_pnls else 0.0,
        "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        "best": max(realized_pnls) if realized_pnls else 0.0,
        "worst": min(realized_pnls) if realized_pnls else 0.0,
        "open_positions": open_positions,
    }


def print_report(rep: dict):
    sign = "+" if rep["profit"] >= 0 else ""
    print("=" * 46)
    print("  VÝDĚLEK BOTA (paper)")
    print("=" * 46)
    print(f"  Vložený kapitál   : {rep['start']:>13,.2f}")
    print(f"  Aktuální hodnota  : {rep['equity']:>13,.2f}")
    print(f"  Zisk / ztráta     : {sign}{rep['profit']:>12,.2f}  ({sign}{rep['return_pct']:.2f} %)")
    print("-" * 46)
    print(f"    realizováno   : {rep['realized']:>+11,.2f}  (uzavřené obchody)")
    print(f"    nerealizováno : {rep['unrealized']:>+11,.2f}  (otevřené pozice)")
    print("-" * 46)
    print(f"  Uzavřených obchodů: {rep['n_trades']}"
          f"  (W:{rep['n_wins']} / L:{rep['n_losses']}, win rate {rep['win_rate']:.0f} %)")
    if rep["n_trades"]:
        print(f"  Prům. zisk / ztráta : {rep['avg_win']:+.2f} / {rep['avg_loss']:+.2f}")
        print(f"  Nejlepší / nejhorší : {rep['best']:+.2f} / {rep['worst']:+.2f}")
    if rep["open_positions"]:
        print("-" * 46)
        print(f"  Otevřené pozice ({len(rep['open_positions'])}):")
        for p in rep["open_positions"]:
            pr = f"{p['price']:.4f}" if p["price"] is not None else "n/a"
            print(f"    {p['side']:<5} {p['symbol']:<10} vstup {p['entry']:.4f}"
                  f"  nyní {pr}  pnl {p['pnl']:+.2f}")
    print("=" * 46)


if __name__ == "__main__":
    print_report(build_report(config.DB_PATH))
