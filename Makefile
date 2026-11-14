# Commandes courantes de Marswalk. `make help` pour la liste.
.PHONY: help install dev dev-mock down test test-py test-web lint typecheck contracts \
        contracts-check api-client fictif examples validate ownership db-test

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install: ## Installe les dépendances Python (uv) et web (pnpm)
	uv sync --all-packages
	pnpm install

dev: ## Lance PostGIS, l'API et le front avec Docker Compose
	docker compose up --build

dev-mock: ## Lance le front seul avec le faux serveur (MSW) et le site fictif
	pnpm dev:mock

down: ## Arrête l'environnement Docker
	docker compose down

test: lint typecheck contracts-check test-py test-web ## Tout ce que vérifie l'intégration continue

test-py: ## Tests Python (les tests PostGIS demandent MARSWALK_DATABASE_URL)
	uv run pytest

test-web: ## Tests du front
	pnpm test

lint: ## Lint Python et TypeScript
	uv run ruff check .
	uv run ruff format --check .
	pnpm lint

typecheck: ## mypy strict et tsc --noEmit
	uv run mypy packages/core pipeline planner conditions api tools
	pnpm typecheck

contracts: ## Réexporte contracts/ (OpenAPI et schémas) puis régénère le client TypeScript
	uv run python tools/export_contracts.py
	pnpm gen:api

contracts-check: ## Échoue si les contrats ou le client TypeScript ont dérivé
	uv run python tools/export_contracts.py --check
	pnpm gen:api
	git diff --exit-code -- web/src/shared/api/schema.d.ts

api-client: ## Génère le client TypeScript depuis contracts/openapi.json
	pnpm gen:api

fictif: ## Régénère le paquet du site fictif (fixtures/sites/fictif)
	uv run python tools/make_fictif.py

examples: ## Régénère contracts/examples (changement de contrat seulement)
	uv run python tools/make_examples.py

validate: ## Valide le paquet du site fictif
	uv run python tools/validate_site_package.py fixtures/sites/fictif --max-mb 30

ownership: ## Contrôle de propriété de la branche courante contre origin/main
	uv run python tools/check_ownership.py --base origin/main

db-test: ## Teste la migration sur le PostGIS de docker compose
	docker compose up -d db
	MARSWALK_DATABASE_URL=postgresql+psycopg://marswalk:marswalk@localhost:5432/marswalk uv run pytest -m db
