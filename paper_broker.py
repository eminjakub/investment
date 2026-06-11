"""Paper broker – simulace plnění, portfolio, exity a sledování výsledků.

Žádné reálné peníze, žádné reálné příkazy. Ceny tahá z burzy přes CCXT
(public data, bez klíče). Pro každý otevřený obchod navíc zaznamenává ceny
po 1h/4h/24h => to jsou labely pro pozdější učení (jak to ve skutečnosti dopadlo).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import ccxt

import config
from storage import Storage


@dataclass
class Position:
    signal_id: int
    symbol: str
    side: str
    size_value: float          # USDT alokované do pozice
    entry_price: float
    qty: float
    entry_time: float
    stop: float
    take: float
    outcomes_done: dict = field(default_factory=dict)  # horizon -> bool


class PaperBroker:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.cash = config.STARTING_CAPITAL
        self.positions: dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.daily_pnl = 0.0
        self._day = time.strftime("%Y-%m-%d")
        self.exchange = getattr(ccxt, config.PRICE_EXCHANGE)()
        self._load_state()   # obnov stav z DB po případném restartu

    def _load_state(self):
        """Obnoví stav z DB po restartu. Bez tohohle žije evidence otevřených
        pozic jen v paměti procesu – po restartu by se „zapomněly" (přestaly by
        se hlídat exity) a no-stacking pojistka by nezabránila duplicitě
        (long + short na stejný symbol). Přesně to způsobí 2 BTC pozice po restartu.
        """
        self.realized_pnl = self.storage.total_realized()
        self.cash = config.STARTING_CAPITAL + self.realized_pnl
        for row in self.storage.get_open_positions():
            codes = (row["currencies"] or "").split(",")
            symbol = next((config.TRACKED_ASSETS[c] for c in codes
                           if c in config.TRACKED_ASSETS), None)
            if symbol is None or symbol in self.positions:
                continue  # dict drží max. jednu pozici na symbol
            entry = row["entry_price"]
            side = row["side"]
            size_value = row["size_value"]
            if side == "long":
                stop = entry * (1 - config.STOP_LOSS_PCT)
                take = entry * (1 + config.TAKE_PROFIT_PCT)
            else:
                stop = entry * (1 + config.STOP_LOSS_PCT)
                take = entry * (1 - config.TAKE_PROFIT_PCT)
            try:
                entry_time = time.mktime(time.strptime(row["ts"], "%Y-%m-%d %H:%M:%S"))
            except (ValueError, TypeError):
                entry_time = time.time()
            outcomes_done = {h: (row[f"price_{h}"] is not None)
                             for h in config.OUTCOME_HORIZONS}
            self.positions[symbol] = Position(
                signal_id=row["id"], symbol=symbol, side=side, size_value=size_value,
                entry_price=entry, qty=size_value / entry, entry_time=entry_time,
                stop=stop, take=take, outcomes_done=outcomes_done,
            )
            self.cash -= size_value
        if self.positions:
            print(f"[broker] obnoveno {len(self.positions)} otevřených pozic z DB "
                  f"| realized {self.realized_pnl:+.2f}")

    # --- ceny ---
    def get_price(self, symbol: str) -> float | None:
        try:
            return float(self.exchange.fetch_ticker(symbol)["last"])
        except Exception as e:
            print(f"[broker] cena {symbol} nedostupná: {e}")
            return None

    # --- otevření pozice (simulovaný fill na aktuální ceně) ---
    def open_position(self, signal_id: int, symbol: str, side: str, size_value: float):
        if symbol in self.positions:  # nikdy nepřepisuj existující pozici (vznikl by orphan)
            print(f"[broker] {symbol} už drží pozici – nové otevření přeskočeno")
            return
        price = self.get_price(symbol)
        if price is None:
            return
        qty = size_value / price
        if side == "long":
            stop = price * (1 - config.STOP_LOSS_PCT)
            take = price * (1 + config.TAKE_PROFIT_PCT)
        else:
            stop = price * (1 + config.STOP_LOSS_PCT)
            take = price * (1 - config.TAKE_PROFIT_PCT)

        self.positions[symbol] = Position(
            signal_id=signal_id, symbol=symbol, side=side, size_value=size_value,
            entry_price=price, qty=qty, entry_time=time.time(), stop=stop, take=take,
        )
        self.cash -= size_value
        self.storage.set_entry(signal_id, price)
        print(f"[broker] OPEN {side} {symbol} @ {price:.4f} (size {size_value:.0f})")

    def _pnl(self, pos: Position, price: float) -> float:
        diff = (price - pos.entry_price) if pos.side == "long" else (pos.entry_price - price)
        return diff * pos.qty

    # --- pravidelný přepočet: labely výsledků + exity ---
    def update(self, now: float):
        self._roll_day()
        for symbol, pos in list(self.positions.items()):
            price = self.get_price(symbol)
            if price is None:
                continue

            # 1) labely výsledku (1h/4h/24h od vstupu) – pro učení
            for name, secs in config.OUTCOME_HORIZONS.items():
                if not pos.outcomes_done.get(name) and now - pos.entry_time >= secs:
                    self.storage.set_outcome(pos.signal_id, name, price, self._pnl(pos, price))
                    pos.outcomes_done[name] = True

            # 2) exity (stop-loss / take-profit / max-hold)
            exit_reason = None
            if pos.side == "long":
                if price <= pos.stop:
                    exit_reason = "stop-loss"
                elif price >= pos.take:
                    exit_reason = "take-profit"
            else:
                if price >= pos.stop:
                    exit_reason = "stop-loss"
                elif price <= pos.take:
                    exit_reason = "take-profit"
            if exit_reason is None and now - pos.entry_time >= config.MAX_HOLD_SECONDS:
                exit_reason = "max-hold"

            if exit_reason:
                self._close(pos, price, exit_reason)

    def _close(self, pos: Position, price: float, reason: str):
        pnl = self._pnl(pos, price)
        self.cash += pos.size_value + pnl
        self.realized_pnl += pnl
        self.daily_pnl += pnl
        tag = ("zisk" if pnl > 0 else "ztráta") + "/" + reason
        self.storage.set_exit(pos.signal_id, price, reason, pnl, tag)
        del self.positions[pos.symbol]
        print(f"[broker] CLOSE {pos.symbol} @ {price:.4f} | {reason} | pnl {pnl:+.2f}")

    # --- pomocné ---
    def equity(self) -> float:
        held = 0.0
        for pos in self.positions.values():
            price = self.get_price(pos.symbol) or pos.entry_price
            held += pos.size_value + self._pnl(pos, price)
        return self.cash + held

    def _roll_day(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._day:
            self._day = today
            self.daily_pnl = 0.0  # reset denního kill switche
