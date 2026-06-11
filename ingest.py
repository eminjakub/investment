"""Sběr zpráv z veřejných RSS feedů crypto médií.

PROČ RSS místo API s klíčem:
- zadarmo, bez registrace, bez API klíče,
- BEZ měsíčního limitu (CryptoCompare free = 100 callů/MĚSÍC, což polling bot
  sní za ~1,5 h – proto to dřív po hodině umřelo).
- Můžeš pollovat jak často chceš; RSS jsou staticky cachované soubory.

Robustnost: stahuje se z víc zdrojů. Když jeden feed spadne / je nedostupný,
jen se zaloguje a jede se z ostatních. Přidat/ubrat zdroj = uprav FEEDS.
Jiný typ zdroje (jiné API) = přepíšeš jen tenhle soubor.
"""
from __future__ import annotations

import feedparser

import config
from models import NewsItem

# Browser-like UA – některé feedy (Cloudflare) blokují defaultní UA knihoven.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# (název zdroje, URL feedu). Když některý dlouhodobě nefunguje, zakomentuj ho.
FEEDS = [
    ("Cointelegraph",  "https://cointelegraph.com/rss"),
    ("Decrypt",        "https://decrypt.co/feed"),
    ("CryptoBriefing", "https://cryptobriefing.com/feed"),
    ("crypto.news",    "https://crypto.news/feed"),
    ("CoinDesk",       "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
]

# RSS píše "Bitcoin", ne "BTC" → mapujeme klíčová slova na ticker.
ASSET_KEYWORDS = {
    "BTC":  ("bitcoin", "btc"),
    "ETH":  ("ethereum", "ether", "eth"),
    "SOL":  ("solana", "sol"),
    "XRP":  ("xrp", "ripple"),
    "DOGE": ("dogecoin", "doge"),
}


def _detect_assets(text: str) -> list[str]:
    """Z titulku/textu vytáhne, kterých sledovaných aktiv se zpráva týká."""
    t = text.lower()
    found = []
    for ticker, kws in ASSET_KEYWORDS.items():
        if ticker in config.TRACKED_ASSETS and any(kw in t for kw in kws):
            found.append(ticker)
    return found


def fetch_news(seen_ids: set[str]) -> list[NewsItem]:
    """Vrátí nové (dosud neviděné) zprávy ze všech feedů.

    Chyby jednotlivých feedů se jen zalogují, smyčka pokračuje dál.
    """
    items: list[NewsItem] = []
    total_entries = 0
    ok_feeds = 0

    for name, url in FEEDS:
        try:
            parsed = feedparser.parse(url, agent=_UA)
        except Exception as e:
            print(f"[ingest] feed {name}: chyba {e}")
            continue

        if parsed.bozo and not parsed.entries:
            print(f"[ingest] feed {name}: nenačten "
                  f"({parsed.get('bozo_exception', '?')})")
            continue

        ok_feeds += 1
        total_entries += len(parsed.entries)
        for entry in parsed.entries:
            pid = entry.get("id") or entry.get("link", "")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            items.append(NewsItem(
                id=pid,
                title=title,
                url=entry.get("link", ""),
                source=name,
                currencies=_detect_assets(f"{title} {summary}"),
                published_at=str(entry.get("published", "")),
            ))

    if ok_feeds == 0:
        print("[ingest] POZOR: nenačten žádný feed (síť/DNS/blokace?).")
    elif total_entries == 0:
        print("[ingest] feedy načteny, ale 0 položek.")
    return items
