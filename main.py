r"""Vstupní bod – propojí všech 5 modulů do jedné smyčky.

PAPER ONLY. Cíl týdne 1: ověřit, že to běží a dávají signály smysl –
NE jestli to vydělává (týden není statisticky vzorek). Spouštěj klidně pod
tmux / nohup; Ctrl-C běh ukončí a vypíše souhrn.

Tok jedné zprávy:
    ingest -> triage -> (LLM) analysis -> risk -> paper_broker
                                  \-> storage (log všeho, i skipnutého)
"""
from __future__ import annotations

import signal
import time

from openai import OpenAI

import analysis as analysis_mod
import config
import ingest
import report
import risk
import triage
from paper_broker import PaperBroker
from storage import Storage


def _graceful_stop(signum, frame):
    """SIGTERM (např. `systemctl stop`) → korektní ukončení vč. finálního reportu."""
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _graceful_stop)  # ať `systemctl stop` ukončí čistě

    if not config.LLM_API_KEY and "localhost" not in config.LLM_BASE_URL:
        print("[pozor] LLM_API_KEY není nastaven – u hostovaných poskytovatelů "
              "(Groq/Gemini) je potřeba (free klíč viz README).")

    storage = Storage(config.DB_PATH)
    broker = PaperBroker(storage)
    client = OpenAI(base_url=config.LLM_BASE_URL,
                    api_key=config.LLM_API_KEY or "not-needed")

    seen_ids: set[str] = set()
    start = time.time()
    last_poll = 0.0
    last_hb = 0.0

    print(f"== Paper bot start | kapitál {config.STARTING_CAPITAL:.0f} | "
          f"ceny z {config.PRICE_EXCHANGE} | model {config.LLM_MODEL} ==")
    print("Ctrl-C pro ukončení.\n")

    try:
        while True:
            now = time.time()

            # 1) nové zprávy (jen jednou za POLL_INTERVAL)
            if now - last_poll >= config.POLL_INTERVAL_SECONDS:
                last_poll = now
                for item in ingest.fetch_news(seen_ids):
                    ok, reason = triage.passes_triage(item)
                    if not ok:
                        continue
                    print(f"[news] {item.title[:80]}  ({reason})")

                    result = analysis_mod.analyze(item, client)
                    if result is None:
                        continue

                    decision = risk.evaluate(result, broker)
                    sid = storage.log_signal(item, reason, result, decision)
                    print(f"   -> {result.direction} conf={result.confidence:.2f}"
                          f" | {decision.action}: {decision.reason}")

                    if decision.action == "open":
                        broker.open_position(sid, decision.symbol,
                                             decision.side, decision.size_value)

            # 2) přepočet pozic: labely výsledků + exity (běží i bez zpráv)
            broker.update(now)

            # 3) heartbeat (ať vidíš, že žije i v tichu + jak si stojí)
            if now - last_hb >= config.HEARTBEAT_SECONDS:
                last_hb = now
                eq = broker.equity()
                ret = (eq - config.STARTING_CAPITAL) / config.STARTING_CAPITAL * 100
                print(f"[hb] {time.strftime('%H:%M:%S')} | pozic={len(broker.positions)}"
                      f" | equity={eq:,.0f} ({ret:+.2f} %) | realized={broker.realized_pnl:+.0f}")

            # 4) auto-stop po týdnu
            if config.MAX_RUNTIME_SECONDS and now - start >= config.MAX_RUNTIME_SECONDS:
                print("\n== Dosažen MAX_RUNTIME, končím ==")
                break

            time.sleep(config.TICK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n== Ukončeno uživatelem ==")
    finally:
        broker.update(time.time())   # poslední přepočet pozic
        storage.close()
        print()
        report.print_report(report.build_report(config.DB_PATH))
        print(f"Detaily v DB: {config.DB_PATH} (tabulka signals)")


if __name__ == "__main__":
    main()
