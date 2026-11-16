#!/bin/sh
# Entrypoint de production de l'API Marswalk.
# Attend que PostgreSQL soit prêt avant de lancer la migration Alembic,
# puis démarre Uvicorn (MARSWALK_WORKERS, 1 par défaut).
set -e

if [ -n "$MARSWALK_DATABASE_URL" ]; then
    echo "[entrypoint] Attente de PostgreSQL…"
    MAX=30
    i=0
    until python - <<'EOF'
import os, sys
try:
    import psycopg
    # psycopg refuse le préfixe SQLAlchemy "postgresql+psycopg://"
    psycopg.connect(os.environ["MARSWALK_DATABASE_URL"].replace("+psycopg", "")).close()
    sys.exit(0)
except Exception:
    sys.exit(1)
EOF
    do
        i=$((i + 1))
        if [ "$i" -ge "$MAX" ]; then
            echo "[entrypoint] PostgreSQL injoignable après $MAX tentatives. Abandon." >&2
            exit 1
        fi
        echo "[entrypoint] tentative $i/$MAX — nouvelle tentative dans 3 s…"
        sleep 3
    done
    echo "[entrypoint] PostgreSQL prêt. Lancement de la migration Alembic…"
    alembic upgrade head
    echo "[entrypoint] Migration terminée."
fi

# 1 worker par défaut : le warmup de Jezero prend ~1,4 Go par processus (OOM à 2 workers
# sur 2 Go), et le hub WebSocket des sorties vit en mémoire, propre à chaque processus.
WORKERS="${MARSWALK_WORKERS:-1}"
echo "[entrypoint] Démarrage d'Uvicorn ($WORKERS worker(s))…"
exec uvicorn marswalk_api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --forwarded-allow-ips="*" \
    --proxy-headers
