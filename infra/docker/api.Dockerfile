# API Marswalk (FastAPI). Contexte de construction : racine du dépôt.
FROM python:3.12-slim
# libexpat1 : demandée par la GDAL embarquée dans les roues de rasterio, absente de l'image slim.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 MARSWALK_ROOT=/app PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY packages/core/pyproject.toml packages/core/
COPY pipeline/pyproject.toml pipeline/
COPY planner/pyproject.toml planner/
COPY conditions/pyproject.toml conditions/
COPY api/pyproject.toml api/
RUN mkdir -p packages/core/marswalk_core pipeline/marswalk_pipeline planner/marswalk_planner \
      conditions/marswalk_conditions api/marswalk_api \
 && uv sync --frozen --no-dev --all-packages --no-install-workspace
COPY . .
RUN uv sync --frozen --no-dev --all-packages
WORKDIR /app/api
EXPOSE 8000
CMD ["sh", "-c", "if [ -n \"$MARSWALK_DATABASE_URL\" ]; then alembic upgrade head; fi && uvicorn marswalk_api.main:app --host 0.0.0.0 --port 8000"]
