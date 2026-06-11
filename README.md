# News Trading Bot — v1 (paper)

Plně paper ("nanečisto") prototyp obchodního bota: čte krypto zprávy, nechá LLM
odhadnout dopad a na základě toho **simuluje** obchody. **Žádné reálné peníze,
žádné reálné příkazy** — v kódu není ani řádek živé exekuce, a to schválně.

## ⚠️ Na rovinu, ať to čteš správně

- **Týdenní běh ti NEŘEKNE, jestli to vydělává.** Za týden padne jen pár signálů
  a režim trhu (býk/medvěd) přebije strategii. K důvěře v edge je potřeba mnoho
  obchodů přes různé podmínky = měsíce, ne týden.
- **Cíl týdne 1 = „běží to a dávají signály smysl?"** Tedy: tahá zprávy, volá
  LLM, generuje signály, simuluje plnění, vše loguje a nespadne; a když ráno
  čteš log, vypadají úsudky rozumně, nebo flaguje blbosti?
- **Učení tu zatím NENÍ — a je to záměr.** Bot teď jen poctivě **loguje** každý
  signál i s výsledkem po 1h/4h/24h. Ten log je semínko pro krok 2 (paměť) a
  krok 3 (statistika) — viz Roadmapa. Z týdne dat se nemá co učit (přeučení na šum).

## Moduly

| Soubor | Role |
|---|---|
| `ingest.py` | Stahování zpráv (veřejné RSS feedy, bez klíče) |
| `triage.py` | Levný filtr – pustit zprávu k drahému LLM? |
| `analysis.py` | LLM (OpenAI-kompatibilní, lze zdarma) → strukturovaný odhad dopadu |
| `risk.py` | Tvrdé pojistky mezi signálem a obchodem |
| `paper_broker.py` | Simulace plnění, portfolio, exity, labely výsledků |
| `storage.py` | SQLite log (= učební korpus) |
| `main.py` | Smyčka, co to celé propojí |

## Rozjezd

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # a vyplň oba tokeny
python main.py
```

Na týdenní běh pusť pod `tmux` / `nohup` / `screen`. `Ctrl-C` ukončí běh a vypíše souhrn.

## Co ladit v `config.py`

Sledovaná aktiva (`TRACKED_ASSETS` = zároveň likviditní whitelist), práh
`MIN_CONFIDENCE`, velikost pozice, `DAILY_LOSS_LIMIT` (kill switch), stop-loss /
take-profit a LLM (`LLM_BASE_URL` + `LLM_MODEL`). Default je **Groq free tier**;
přepnutím base_url pojedeš na Gemini (free) nebo lokální Ollama (offline). Klíč
poskytovatele jde do `.env` jako `LLM_API_KEY`.

## Jak číst výsledky

Vše je v `trading_log.db`, tabulka `signals`. Loguje se **každý analyzovaný
signál** (i ten, co se neobchodoval) + ceny po 1h/4h/24h a výsledek obchodu:

```bash
sqlite3 trading_log.db \
  "SELECT id, title, direction, confidence, decision, pnl_24h, outcome_tag
   FROM signals ORDER BY id DESC LIMIT 20;"
```

## Roadmapa

1. **(teď) Logování** — sbíráme data, ověřujeme plumbing a smysluplnost signálů.
2. **Paměť (retrieval)** — doplnit `storage.find_similar_past_signals()`: k nové
   zprávě najít podobné minulé případy i s výsledky a vložit je LLM do kontextu.
   Učení ze zkušenosti bez trénování.
3. **Statistika + kalibrace** — až bude stovky záznamů: které rysy předpovídají
   zisk, je „vysoká jistota" fakt častěji správně, doladění prahů. Pak teprve ML.

## ⚠️ Důležité

- Edukativní prototyp, **ne investiční rada**.
- Zprávy bere z **veřejných RSS feedů** (CoinDesk, Cointelegraph, Decrypt,
  CryptoBriefing, crypto.news) – zadarmo, **bez API klíče a bez měsíčního
  limitu**. Tahá z víc zdrojů; když jeden spadne, jede z ostatních. Zdroje
  upravíš v seznamu `FEEDS` v `ingest.py`; jiný zdroj/API = měníš jen `fetch_news()`.
- Než bys *kdy* uvažoval o reálných penězích: měsíce v paperu, a pak jen částka,
  kterou si můžeš dovolit ztratit celou.
