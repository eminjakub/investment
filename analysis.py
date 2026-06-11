"""LLM analýza dopadu zprávy přes OpenAI-kompatibilní API.

Funguje s jakýmkoli OpenAI-kompatibilním poskytovatelem – stačí v config.py
nastavit LLM_BASE_URL + LLM_MODEL a v .env LLM_API_KEY. Tím to jede ZADARMO:
  - Groq (rychlé, free):      base_url https://api.groq.com/openai/v1
  - Google Gemini (free):     base_url .../v1beta/openai/
  - Lokální Ollama (offline):  base_url http://localhost:11434/v1  (klíč netřeba)

Model je instruovaný, aby byl skeptický k nepotvrzeným / jednozdrojovým /
pumpovým zprávám a snižoval u nich jistotu (hlavní obrana proti fake news).
Pozn.: striktní JSON prompt + defenzivní parsing s jedním pokusem o opravu.
"""
from __future__ import annotations

import json
from typing import Optional

from openai import OpenAI

import config
from models import Analysis, NewsItem

SYSTEM_PROMPT = """Jsi analytik krypto trhu. Dostaneš krátkou zprávu a odhadneš \
její pravděpodobný KRÁTKODOBÝ dopad na cenu konkrétních aktiv.

Buď skeptický: nepotvrzená oznámení, jediný neznámý zdroj, vágní "partnerství" \
nebo hype kolem malých tokenů často slouží k pump-and-dump. V takových případech \
drž confidence nízko.

Odpověz VÝHRADNĚ jedním JSON objektem, bez úvodu, bez markdownu, v tomto tvaru:
{"tickers": ["BTC"], "direction": "long|short|neutral", "confidence": 0.0-1.0, \
"magnitude": "low|medium|high", "horizon": "hours|days", "reasoning": "stručně"}"""


def analyze(item: NewsItem, client: OpenAI) -> Optional[Analysis]:
    user = (
        f"Zpráva: {item.title}\n"
        f"Dotčená aktiva (dle zdroje): {', '.join(item.currencies) or 'neuvedeno'}\n"
        f"Zdroj: {item.source}"
    )
    try:
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[analysis] chyba LLM: {e}")
        return None

    data = _parse_json(raw)
    if data is None:
        print(f"[analysis] nepodařilo se naparsovat JSON: {raw[:120]}...")
        return None

    try:
        return Analysis(
            tickers=[t.upper() for t in data.get("tickers", []) if isinstance(t, str)],
            direction=str(data.get("direction", "neutral")).lower(),
            confidence=float(data.get("confidence", 0.0)),
            magnitude=str(data.get("magnitude", "low")).lower(),
            horizon=str(data.get("horizon", "")),
            reasoning=str(data.get("reasoning", "")),
            raw=raw,
        )
    except (ValueError, TypeError) as e:
        print(f"[analysis] neplatná pole v JSON: {e}")
        return None


def _parse_json(text: str) -> Optional[dict]:
    """Defenzivní parsing: odstraní ```json``` obaly a zkusí vyříznout {...}."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None
