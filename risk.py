"""Riziková vrstva – tvrdé pojistky mezi signálem a (paper) obchodem.

Tady se rozhoduje BINÁRNĚ a konzervativně. Když cokoli nesedí, neobchoduj.
Tyhle pojistky jsou důležitější než samotná logika signálu – při plné
automatizaci ti drží účet naživu, když se LLM nebo zdroj zprávy splete.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from models import Analysis


@dataclass
class Decision:
    action: str               # "open" | "skip"
    symbol: str = ""          # obchodní pár (CCXT)
    side: str = ""            # "long" | "short"
    size_value: float = 0.0   # velikost v quote měně (USDT)
    reason: str = ""


def evaluate(analysis: Analysis, broker) -> Decision:
    # 1) směr a jistota
    if analysis.direction not in ("long", "short"):
        return Decision("skip", reason="neutrální směr")
    if analysis.confidence < config.MIN_CONFIDENCE:
        return Decision("skip", reason=f"nízká jistota {analysis.confidence:.2f}")

    # 2) vyber první sledovaný ticker (likviditní whitelist)
    ticker = next((t for t in analysis.tickers if t in config.TRACKED_ASSETS), None)
    if ticker is None:
        return Decision("skip", reason="ticker mimo whitelist")
    symbol = config.TRACKED_ASSETS[ticker]

    # 3) kill switch – denní ztráta
    if broker.daily_pnl <= -config.DAILY_LOSS_LIMIT:
        return Decision("skip", reason="kill switch: denní limit ztráty")

    # 4) limity pozic
    if len(broker.positions) >= config.MAX_OPEN_POSITIONS:
        return Decision("skip", reason="max otevřených pozic")
    if symbol in broker.positions:
        return Decision("skip", reason="pozice už existuje")

    # 5) velikost pozice (zlomek kapitálu, zastropováno)
    size = min(broker.cash * config.POSITION_FRACTION, config.MAX_POSITION_VALUE)
    if size <= 0:
        return Decision("skip", reason="nedostatek kapitálu")

    return Decision("open", symbol=symbol, side=analysis.direction,
                    size_value=size, reason="OK")
