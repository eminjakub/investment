# Nasazení na server — krok za krokem

Runbook pro spuštění bota na čistém **Ubuntu** serveru. Předpoklad: máš SSH
přístup (IP + uživatel) a dva klíče — **CryptoCompare** (free) a **LLM klíč**
(free, Groq/Gemini).

---

## 1. Připoj se na server
```bash
ssh UZIVATEL@IP_SERVERU
```

## 2. Dostaň kód na server
Z **tvého PC** (ze složky, kde máš adresář `news_trading_bot`):
```bash
scp -r news_trading_bot UZIVATEL@IP_SERVERU:~/
```
Alternativa: pushni do **privátního** git repa a na serveru `git clone`. Do
`.gitignore` dej `.env` a `*.db`, ať neunikne klíč.

## 3. Připrav prostředí (už na serveru)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
cd ~/news_trading_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 --version        # musí být 3.10+
```

## 4. Vlož API klíče
```bash
cp .env.example .env
nano .env
```
Vyplň a ulož (`Ctrl+O`, `Enter`, `Ctrl+X`):
- `CRYPTOCOMPARE_API_KEY` — free, vygeneruj na https://www.cryptocompare.com/cryptopian/api-keys
- `LLM_API_KEY` — **free**, bez platební karty: Groq (https://console.groq.com/keys)
  nebo Gemini (https://aistudio.google.com/apikey). Poskytovatele a model nastavíš
  v `config.py` (`LLM_BASE_URL` + `LLM_MODEL`); default je Groq. Lokální Ollama?
  Klíč nech prázdný.

## 5. Zkušební spuštění (na popředí)
Než to pustíš natrvalo, ověř, že to naběhne:
```bash
.venv/bin/python main.py
```
Měl bys vidět startovní řádek a po chvíli „heartbeat". Zastav `Ctrl+C`
(vypíše report). Když uvidíš varování o chybějícím klíči nebo chyby stahování,
vrať se ke kroku 4.

## 6. Spuštění jako služba (systemd) — doporučeno
Běží 24/7, sám se zvedne po pádu a přežije reboot.

Nejdřív si zjisti uživatele a cestu pro úpravu service souboru:
```bash
whoami     # -> tahle hodnota patří do  User=
pwd        # jsi v ~/news_trading_bot; tuhle cestu dej do WorkingDirectory a ExecStart
```
Uprav v `newsbot.service` řádky `User=`, `WorkingDirectory=` a `ExecStart=`, pak:
```bash
sudo cp newsbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now newsbot
sudo systemctl status newsbot       # musí být "active (running)"
```

## 7. Sledování, výsledky, zastavení
```bash
journalctl -u newsbot -f                              # živé logy (Ctrl+C jen ukončí sledování, ne bota)
cd ~/news_trading_bot && .venv/bin/python report.py   # kolik "vydělal" (i za běhu)
sudo systemctl stop newsbot                           # zastavit (vypíše finální report do logu)
sudo systemctl start newsbot                          # zase spustit
```

---

## Rychlá alternativa bez systemd (tmux)
```bash
sudo apt install -y tmux
tmux new -s bot
# uvnitř:
cd ~/news_trading_bot && .venv/bin/python main.py
# odpojíš:  Ctrl+B, pak D        | vrátíš se:  tmux attach -t bot
```
Přežije odpojení SSH, ale **ne** reboot.

## Když něco zlobí
- Služba nestartuje → `journalctl -u newsbot --no-pager | tail -30`
- Žádné zprávy → zkontroluj `CRYPTOCOMPARE_API_KEY` v `.env`
- Chyby u cen/obchodů → server potřebuje odchozí HTTPS (Kraken, CryptoCompare, poskytovatel LLM)
- Po naplánovaném týdnu (`MAX_RUNTIME_SECONDS` v `config.py`) se služba sama čistě
  zastaví; pro běh napořád dej `MAX_RUNTIME_SECONDS = None` a v unitu `Restart=always`.
