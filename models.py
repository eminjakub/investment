"""Sdílené datové struktury napříč moduly."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NewsItem:
    """Jedna normalizovaná zpráva (nezávislá na zdroji)."""
    id: str
    title: str
    url: str
    source: str
    currencies: list[str] = field(default_factory=list)
    published_at: str = ""


@dataclass
class Analysis:
    """Strukturovaný výstup LLM analýzy dopadu zprávy."""
    tickers: list[str]
    direction: str          # "long" | "short" | "neutral"
    confidence: float       # 0.0 - 1.0
    magnitude: str          # "low" | "medium" | "high"
    horizon: str            # volný text, např. "hours" / "days"
    reasoning: str
    raw: str = ""           # surová odpověď modelu (pro log)
