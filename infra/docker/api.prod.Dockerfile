# API Marswalk — image de production. Contexte de construction : racine du dépôt.
#
# Différences par rapport à api.Dockerfile (dev) :
#   - Entrypoint dédié avec wait-for-postgres + retry avant migration Alembic
#   - 2 workers Uvicorn (--proxy-headers pour CloudFront/Nginx)
#   - L'image ne contient aucun paquet de site : ils arrivent via un volume Docker.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    MARSWALK_ROOT=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# --- Passe 1 : dépendances (couche mise en cache si les pyproject.toml n'ont pas changé) ---
COPY pyproject.toml uv.lock .python-version ./
COPY packages/core/pyproject.toml packages/core/
COPY pipeline/pyproject.toml         pipeline/
COPY planner/pyproject.toml          planner/
COPY conditions/pyproject.toml       conditions/
COPY api/pyproject.toml              api/
RUN mkdir -p packages/core/marswalk_core pipeline/marswalk_pipeline \
             planner/marswalk_planner conditions/marswalk_conditions \
             api/marswalk_api \
 && uv sync --frozen --no-dev --all-packages --no-install-workspace

# --- Passe 2 : code source ---
COPY . .
# Les fixtures (site fictif, 16 MB) sont dans l'image mais jamais exposées en production
# car MARSWALK_PACKAGES=/app/data/packages écrase le chemin de recherche par défaut.
RUN uv sync --frozen --no-dev --all-packages

# Entrypoint de production (wait-for-postgres + migration + uvicorn)
COPY infra/docker/api.entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app/api
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
