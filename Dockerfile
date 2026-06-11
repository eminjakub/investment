# News trading bot (paper) – kontejner pro Coolify
FROM python:3.12-slim

# Logy ať tečou rovnou do docker/Coolify logs (ne bufferované)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Závislosti (samostatná vrstva kvůli cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kód
COPY . .

# SQLite log míří do /data = persistent volume (přežije redeploy).
# V Coolify přidej Persistent Storage s mount path /data.
ENV DB_PATH=/data/trading_log.db
RUN mkdir -p /data
VOLUME /data

# API klíče se předávají jako Environment Variables (v Coolify UI), NIKDY do image.
# Tohle je background worker – nemá žádný HTTP port.
CMD ["python", "main.py"]
