"""Levný filtr (triage) – rozhodne, jestli zprávu vůbec poslat drahému LLM.

Cíl jediné otázky: 'týká se sledovaného aktiva a může to hýbat trhem?'
Žádné volání LLM, jen práce s řetězci => levné a rychlé. Sem patří případný
malý/levný klasifikátor, až budeš chtít filtr zchytřit.
"""
from __future__ import annotations

import config
from models import NewsItem


def passes_triage(item: NewsItem) -> tuple[bool, str]:
    """Vrátí (projde?, důvod). Důvod se loguje, ať víš, proč co prošlo."""
    title_low = item.title.lower()

    # 1) Týká se to sledovaného aktiva?
    matched = [c for c in item.currencies if c in config.TRACKED_ASSETS]
    if not matched:
        # fallback: zmínka symbolu přímo v titulku
        matched = [c for c in config.TRACKED_ASSETS if c.lower() in title_low]
    if not matched:
        return False, "žádné sledované aktivum"

    # 2) (volitelný signál) obsahuje market-moving klíčové slovo?
    kw = [k for k in config.MOVING_KEYWORDS if k in title_low]
    reason = f"aktiva={matched}" + (f", keywords={kw}" if kw else "")
    return True, reason
