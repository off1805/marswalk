# marswalk

Marswalk est un outil de carte et de planification de sorties à pied sur Mars, centré sur le **cratère Jezero**. Il est réalisé pour le défi « Interplanetary Survival Guide: Martian Map » des NASA Space Apps 2026.

<!-- Section présentation : à écrire par L2. -->

> Le site retenu est Jezero ; `taches-agents.md` est à jour. La feuille de route et le document de besoins, écrits pour Gale, restent valables : partout où ils disent Gale, lire Jezero.

## Démarrer

Prérequis : Python 3.12 avec [uv](https://docs.astral.sh/uv/), Node 22 avec pnpm 10, Docker.

```bash
make install        # dépendances Python et web
docker compose up --build   # PostGIS, API et front (ou : make dev)
```

- Front : http://localhost:5173 (carte du site fictif)
- API : http://localhost:8000/docs

Sans Docker ni API, le front tourne seul sur le faux serveur :

```bash
pnpm install
pnpm dev:mock       # MSW renvoie contracts/examples/, Vite sert les tuiles du site fictif
```

Vérifications de l'intégration continue : `make test` (lint, typage, contrats, tests). Les tests de la migration demandent PostGIS : `make db-test`.

## Organisation du travail

Le projet est découpé en tâches parallèles décrites dans [`taches-agents.md`](taches-agents.md). T00 (ce socle) fixe les contrats ; toutes les autres tâches codent contre ses bouchons et son site fictif.

- Une tâche = une branche `task/<ID>-<slug>` et une PR `[<ID>] <titre>`.
- Une tâche ne modifie que ses chemins (`tasks/ownership.yaml`). Le contrôle `tools/check_ownership.py` le vérifie dans la CI.
- Les contrats sont gelés après la fusion de T00 (étiquette `contrats-v1`, puis `contrats-v2` pour l'interface web unique) : `contracts/`, `packages/core/marswalk_core/schemas.py`, `web/src/shared/store.ts`, `web/src/app/registry.ts`, `web/src/app/feature.ts` et la migration. Un besoin de changement passe par [`tasks/change-requests/`](tasks/change-requests/README.md).
- Le scénario de démo, critère d'acceptation commun : [`docs/scenario-demo.md`](docs/scenario-demo.md).

## Structure

| Chemin | Contenu |
| --- | --- |
| `contracts/` | `openapi.json`, schémas JSON du manifeste et des messages WebSocket, `examples/` (réponses des bouchons) |
| `config/` | `safety.yaml`, `suit.yaml`, `presets.yaml`, `sites/<site_id>/site.yaml` |
| `fixtures/sites/fictif/` | Paquet complet du site fictif (2 x 2 km à 2 m, centré sur Jezero, 17 couches) |
| `packages/core/` | `marswalk_core` : schémas Pydantic (source de vérité), lecture des paquets, géodésie et temps (C1) |
| `pipeline/` | `marswalk_pipeline` : ingest et coreg (D1), derived (D2), package (D3), ground_images (G1) |
| `planner/` | `marswalk_planner` : risque et coût (P1), itinéraire (P2), marche et budgets (P3) |
| `conditions/` | `marswalk_conditions` : conditions et scénarios (K1) |
| `api/` | `marswalk_api` : FastAPI, routeurs par tâche, base PostGIS et migration Alembic |
| `web/` | Front React : coquille (`src/app`), partagé (`src/shared`), fonctionnalités (`src/features/<nom>`) |
| `tools/` | Générateur du site fictif, export des contrats, validateur de paquet, contrôle de propriété |
| `infra/` | Docker Compose (T00), déploiement (L1) |
| `docs/` | Scénario de démo, science (S1), pitch (L2) |

Les chemins de la section 3 de `taches-agents.md` sont rapportés aux paquets Python : `pipeline/ingest/` y désigne `pipeline/marswalk_pipeline/ingest/`, et ainsi de suite. Les tâches qui partagent un dossier mettent leurs tests et leur README dans un sous-dossier à leur nom (`planner/tests/p1/`, `api/tests/a2/`) et leurs modules privés dans `_<id>/` ou `services/<id>/`.

## Règles géographiques

- **R1. Calcul en mètres** dans le système d'analyse du site : `+proj=eqc +lat_ts=<lat> +lon_0=<lon> +R=3396190 +units=m +no_defs` (`analysis_crs` du manifeste).
- **R2. Échanges en degrés** : longitude et latitude planétocentriques est, Mars 2000 (IAU_2015:49900), points écrits `[lon, lat]`. En base, SRID personnalisé `949900`.
- **R3. Affichage en pseudo-Mercator** : tuiles WebMercatorQuad appliquées aux coordonnées martiennes ; toute distance passe par `geodesy` (C1), jamais par MapLibre ou Turf.

## Site fictif

Généré par `tools/make_fictif.py` (déterministe) et validé par `tools/validate_site_package.py`. Il contient un plateau limité par une falaise (comme le front du delta), un petit cratère au bord abrupt, un champ de dunes à faible inertie thermique, un chaos de blocs, deux unités minérales (argiles et carbonates, olivine), un habitat et quatre cibles. Toutes les couches portent `source.instrument = "SYNTHETIC"`.

## Choix de T00 à connaître

Ces points précisent les contrats là où `taches-agents.md` laissait un choix :

- **Routes ajoutées** : `GET /api/presets` (préréglages d'affichage), `GET /api/sites/{site_id}/vector/{layer_id}` (couches vectorielles du paquet) et `GET /api/_contracts/ws-message` (documente les messages du WebSocket dans l'OpenAPI, pour le client TypeScript). Elles appartiennent à A1, sauf la dernière (T00).
- **Paramètre `preset` des zones dangereuses** : il choisit un préréglage de sécurité de `config/safety.yaml` (`standard`, `prudent`), distinct des préréglages d'affichage de `config/presets.yaml`.
- **Base de données** : en plus des six tables prévues, `site_settings` (réglages persistés par `PUT /settings`) et `obstacles` (obstacles signalés pendant une sortie).
- **Bibliothèques** : `marswalk_conditions.list_scenarios()` sert `GET /api/scenarios`. `RouteOptions` porte la combinaison, les conditions et le point d'arrivée pour `plan_variants`. Les grilles NumPy partagées sont dans `marswalk_core/grids.py`.
- **Front** : une fonctionnalité peut fournir `mapSources` comme liste ou comme fonction du contexte, et un `setup()` appelé au démarrage (service worker de F7). Il n'y a qu'une interface web, avec deux vues : la carte (`/`) et la 3D (`/3d`) ; ni tablette, ni HUD. F7 branche Workbox dans `web/src/features/offline/vite.ts`.
- **Temps** : `GET /api/time` prend `site_id` en paramètre (par défaut `fictif`).
