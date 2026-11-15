#!/bin/sh
# Entrypoint de production de l'API Marswalk.
# Attend que PostgreSQL soit prêt avant de lancer la migration Alembic,
# puis démarre Uvicorn avec 2 workers (adapté à une instance 2 GB).
set -e

if [ -n "$MARSWALK_DATABASE_URL" ]; then
    echo "[entrypoint] Attente de PostgreSQL…"
    MAX=30
    i=0
    until python - <<'EOF'
import os, sys
try:
    import psycopg
    psycopg.connect(os.environ["MARSWALK_DATABASE_URL"]).close()
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

echo "[entrypoint] Démarrage d'Uvicorn (2 workers)…"
exec uvicorn marswalk_api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --forwarded-allow-ips="*" \
    --proxy-headers
