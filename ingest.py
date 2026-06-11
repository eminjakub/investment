"""Sběr zpráv z CryptoCompare / CCData (free tier).

Náhrada za CryptoPanic (ten zrušil free API plán k 1. 4. 2026). CryptoCompare
nabízí free news endpoint, agreguje 150+ zdrojů a vrací strukturovaný JSON.
Free API klíč si vygeneruješ na https://www.cryptocompare.com/cryptopian/api-keys
(endpoint funguje i bez klíče s nižším rate limitem, ale klíč se doporučuje).

Stahujeme všechny EN zprávy a relevanci řeší až triage (match na sledovaná
aktiva). Celá závislost na zdroji je schválně jen tady – chceš-li jiný zdroj
(RSS, jiné API), přepíšeš jen funkci fetch_news().
"""
from __future__ import annotations

import requests

import config
from models import NewsItem

API_URL = "https://min-api.cryptocompare.com/data/v2/news/"


def fetch_news(seen_ids: set[str]) -> list[NewsItem]:
    """Vrátí nové (dosud neviděné) zprávy."""
    headers = {}
    if config.CRYPTOCOMPARE_API_KEY:
        headers["Authorization"] = f"Apikey {config.CRYPTOCOMPARE_API_KEY}"

    try:
        resp = requests.get(API_URL, params={"lang": "EN"},
                            headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # síť/parse chyba nesmí položit týdenní běh
        print(f"[ingest] chyba při stahování zpráv: {e}")
        return []

    items: list[NewsItem] = []
    for post in data.get("Data", []):
        pid = str(post.get("id", ""))
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)

        # kategorie jsou pipe-separated, např. "BTC|ETH|Trading"
        cats = (post.get("categories", "") or "").upper().split("|")
        currencies = [c for c in cats if c in config.TRACKED_ASSETS]

        source = (post.get("source_info") or {}).get("name") or post.get("source", "")

        items.append(NewsItem(
            id=pid,
            title=post.get("title", ""),
            url=post.get("url", ""),
            source=source,
            currencies=currencies,
            published_at=str(post.get("published_on", "")),
        ))
    return items
