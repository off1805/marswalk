# Marswalk : tâches pour agents IA en parallèle

12 novembre 2026, mis à jour le 14 novembre 2026 : le site retenu est le cratère Jezero.

Ce document découpe la feuille de route corrigée (`feuille-de-route-revue.md`) en tâches qu'un agent IA peut réaliser seul, chacune sur sa branche, et dont la fusion donne le projet final. Il contient deux choses :

- **Les contrats communs** (sections 2 à 8). Ils fixent d'avance tout ce qui est partagé : dossiers, systèmes de coordonnées, format des couches, API, interfaces de code. La tâche T00 les implémente, puis ils sont gelés. Aucun autre agent ne les modifie.
- **Les fiches de tâches** (section 10). Chacune dit ce que l'agent possède, ce qu'il lit, ce qu'il livre et comment on vérifie que c'est fini.

Le travail démarre une fois le jeu de données obtenu. Seules D1 et I1 ont besoin des vraies données ; tout le reste se développe sur le site fictif fourni par T00.

## 1. Comment s'en servir

1. Lancer un agent sur **T00** seul. Relire et fusionner sa branche, puis poser l'étiquette `contrats-v1`.
2. Lancer en parallèle autant d'agents que voulu sur les tâches de la **vague 1**, en commençant par les chemins critiques (section 2). Chaque agent reçoit le texte de la section 11 suivi de sa fiche.
3. Fusionner dans l'ordre de la section 2. Une tâche n'est fusionnée que si l'intégration continue est verte, y compris le contrôle de propriété des dossiers.
4. Quand D1 à D3 sont fusionnées et le recalage validé dans QGIS, lancer **I1**, puis **I2**, puis **L1** et **L2**.

## 2. Vagues, dépendances et ordre de fusion

| Vague | Tâches | Démarre quand | Notes |
| --- | --- | --- | --- |
| 0 | T00 | Tout de suite | Seule tâche séquentielle. Tout le reste en dépend |
| 1 | C1, P1, P2, P3, K1, D1, D2, D3, A1, A2, A3, A4, F1, F2, F3, F4, F5, F6, F7, S1, G1, X1 | T00 fusionnée | Toutes en parallèle. Chacune code contre les bouchons et le site fictif de T00 |
| 2 | I1 | D1, D2, D3, P1, P2, P3 fusionnées et recalage validé | Bascule sur Jezero et calibration |
| 3 | I2 | Toutes les tâches M et S fusionnées, I1 fusionnée | Tests de bout en bout, puis gel |
| 4 | L1, L2 | I2 fusionnée | Livraison |
| Bonus | X2, X3, X4 | Jalon J2 atteint | Abandonnables sans effet sur le reste |

**Ordre de fusion recommandé dans la vague 1.** Les dépendances passent par des bouchons, donc l'ordre n'est pas obligatoire, mais fusionner les bibliothèques avant leurs consommateurs fait passer les tests d'intégration plus tôt :

1. Bibliothèques : C1, P1, P3, K1, D2, D3
2. Moteur et données : P2, D1, G1 (partie données)
3. API : A1, A2, A3, A4, X1
4. Front : F1, puis F2, F3, F4, F5, F6, F7 dans n'importe quel ordre
5. Contenu : S1 (à tout moment)

Avant chaque fusion, l'agent rebase sa branche sur `main` et relance les tests.

**Chemins critiques à démarrer en premier :**
- T00, D1, puis validation du recalage, puis I1
- T00, P1 et P2, A2, F2, A4 et F5, I2

**Si le nombre d'agents est limité**, lancer par lots : lot 1 = P1, P2, P3, D1, D2, D3, C1 ; lot 2 = A1, A2, A3, A4, K1, S1 ; lot 3 = F1 à F7 ; lot 4 = G1, X1.

## 3. Structure du monorepo et propriété des dossiers

```
marswalk/
├── contracts/                  T00 : schéma OpenAPI exporté, schémas JSON, exemples de charges utiles
├── config/
│   ├── safety.yaml             T00 crée, P1 règle les valeurs par défaut
│   ├── suit.yaml               T00 crée, P3 règle les valeurs par défaut
│   ├── presets.yaml            T00 crée, F1 règle les valeurs par défaut
│   └── sites/<site_id>/site.yaml   T00 (fictif), D1 (jezero)
├── fixtures/sites/fictif/      T00 : paquet de site fictif complet, versionné dans Git
├── data/                       DVC, hors Git : raw/, work/, packages/<site_id>/
├── packages/core/              Python marswalk_core
│   ├── schemas.py              T00 : modèles Pydantic, source de vérité
│   ├── site_package.py         T00 : lecture du manifeste et des COG
│   ├── marstime.py             C1
│   └── geodesy.py              C1
├── pipeline/                   Python marswalk_pipeline
│   ├── ingest/, coreg/         D1
│   ├── derived/                D2
│   ├── package/                D3
│   └── ground_images/          G1
├── planner/                    Python marswalk_planner
│   ├── cost.py, hazards.py     P1
│   ├── route.py, order.py, variants.py   P2
│   └── walk.py, budget.py, return_field.py   P3
├── conditions/                 Python marswalk_conditions : K1
├── api/marswalk_api/
│   ├── main.py, db/, deps.py   T00 (tous les routeurs déjà enregistrés, migration initiale complète)
│   └── routers/
│       ├── sites.py, query.py, tiles.py      A1
│       ├── targets.py, plans.py, hazards.py  A2
│       ├── alerts.py, ws.py, conditions.py, time.py   A3
│       ├── eva.py              A4
│       ├── ground_images.py    G1
│       └── export.py           X1
├── web/src/
│   ├── app/                    T00 : coquille, routes, mise en page, registre des fonctionnalités
│   ├── shared/                 T00 : client API généré, magasin partagé, jetons de design, composants de base
│   ├── shared/marstime.ts, shared/geodesy.ts   C1
│   └── features/
│       ├── map/                F1
│       ├── targets/            F2
│       ├── profile/            F3
│       ├── safety/             F4
│       ├── hud/                F5
│       ├── terrain3d/          F6
│       ├── offline/            F7
│       ├── ground-images/      G1
│       └── export/             X1
├── e2e/                        I2
├── infra/                      T00 (docker compose), L1 (déploiement)
├── docs/
│   ├── scenario-demo.md        T00
│   ├── science/                S1
│   └── pitch/                  L2
└── tasks/ownership.yaml        T00 : la carte de propriété lue par l'intégration continue
```

**Règle de propriété.** Une tâche ne crée ou ne modifie que les chemins qu'elle possède, plus ses propres tests à l'intérieur de ces chemins. Le script `tools/check_ownership.py`, lancé par l'intégration continue, compare les fichiers modifiés d'une branche `task/<ID>-...` à `tasks/ownership.yaml` et échoue en cas de débordement. Les fichiers partagés (`pyproject.toml` racine, `package.json` racine, `pnpm-lock.yaml`, `uv.lock`) font exception pour l'ajout de dépendances seulement ; en cas de conflit de verrou, régénérer le fichier après rebase au lieu de le fusionner à la main.

## 4. Règles géographiques

Ces trois règles évitent les erreurs de projection, la cause la plus fréquente de couches décalées et de distances fausses.

**R1. Calcul en mètres.** Tout calcul (pente, rugosité, coût, itinéraire, distances) se fait dans le système d'analyse du site, une projection équirectangulaire sur la sphère Mars 2000 centrée sur le site :
`+proj=eqc +lat_ts=<lat_centre> +lon_0=<lon_centre> +R=3396190 +units=m +no_defs`.
La chaîne exacte est dans `site.yaml` (`analysis_crs`). La grille d'analyse est celle du MNT : résolution 1 m pour les couches, 2 m pour la planification.

**R2. Échanges en degrés.** Toute coordonnée qui traverse l'API ou un fichier GeoJSON est en longitude et latitude planétocentriques, longitudes est de -180 à 180, référentiel Mars 2000 (IAU_2015:49900). Le GeoJSON dérogera donc à la norme, qui suppose WGS 84 ; c'est assumé et documenté.

**R3. Affichage en pseudo-Mercator.** Les tuiles d'affichage sont découpées selon la grille WebMercatorQuad appliquée aux longitudes et latitudes martiennes, comme le font Mars Trek et OpenPlanetary : MapLibre et deck.gl affichent ainsi les bonnes coordonnées martiennes. En contrepartie, toute distance, toute surface et l'échelle doivent être calculées avec le rayon martien (3 389,5 km en moyenne, ou 3 396,19 km pour la sphère Mars 2000) grâce aux fonctions de `geodesy` (C1), jamais avec celles de MapLibre ou de Turf. La barre d'échelle native de MapLibre est désactivée.

**Niveaux de zoom.** À l'équateur, la taille d'un pixel au zoom z vaut `360 × 59 274 / (256 × 2^z)` mètres martiens. D'où : HiRISE (0,25 m) zoom maximal 19, couches à 1 m zoom 17, CTX (6 m) zoom 14, MOLA zoom 10. Le zoom minimal de toutes les couches du site est 12.

## 5. Paquet de site et catalogue des couches

### 5.1 Contenu d'un paquet

```
packages/<site_id>/
├── manifest.json               décrit le site et chaque couche (schéma : contracts/site-manifest.schema.json)
├── cog/<layer_id>.tif          COG Float32 sur la grille d'analyse, nodata -9999 (pour les valeurs et le calcul)
├── tiles/<layer_id>/{z}/{x}/{y}.webp   tuiles d'affichage pré-rendues avec la palette de la couche
├── tiles/terrain_rgb/{z}/{x}/{y}.png   altitude encodée en terrain-RGB pour la 3D
├── vector/<layer_id>.geojson   couches vectorielles (traverse du rover, images au sol, cibles proposées)
└── thumbs/                     vignettes des images au sol (G1)
```

Taille totale inférieure à 2 Go (ENF-10), vérifiée par le validateur.

### 5.2 Manifeste

Champs du site : `site_id`, `name`, `bbox` (degrés), `analysis_crs`, `grid` (résolution, largeur, hauteur, transformation affine), `habitat` (point), `rover` (point, facultatif), `mission_epoch_utc` (début du sol 1 de la mission simulée), `default_preset`.

Champs de chaque couche :

| Champ | Exemple | Rôle |
| --- | --- | --- |
| `id` | `slope` | Identifiant fixe (liste ci-dessous) |
| `title`, `kind` | « Pente », `derived` | Affichage et regroupement (`imagery`, `dem`, `derived`, `thermal`, `spectral`, `vector`, `ground`) |
| `unit`, `value_range` | `deg`, `[0, 60]` | Légende et interrogation |
| `resolution_m`, `acquired` | `1.0`, `2014-03-02` | Affichés à côté de la couche (ENF-03) |
| `source` | instrument, mission, identifiant du produit PDS, URL | Traçabilité (ENF-04) |
| `uncertainty` | `{ "value": 0.5, "unit": "deg", "coreg_m": 3.0 }` | Incertitude de mesure et de recalage (ENF-04) |
| `legend` | `{ "type": "continuous", "stops": [...] }` ou `categorical` | Légende commune 2D et 3D |
| `cog`, `tiles` | chemins, `minzoom`, `maxzoom`, `format` | Accès aux données |
| `status` | `ok`, `missing`, `degraded` | Dégradation gracieuse (ENF-07) |

### 5.3 Identifiants de couches

| `id` | Contenu | Produit par |
| --- | --- | --- |
| `hirise_vis` | Imagerie HiRISE (niveaux de gris ou couleur) | D1, D3 |
| `ctx_vis` | Contexte CTX | D1, D3 |
| `dem` | MNT HiRISE (ou repli CTX ou MOLA), altitude en m | D1 |
| `dem_mola` | MOLA, repli et horizon | D1 |
| `slope` | Pente en degrés | D2 |
| `roughness` | Rugosité en m (écart type local) | D2 |
| `hillshade` | Ombrage | D2 |
| `obstacles` | Masque d'obstacles avec tampon, 0 ou 1 | D2 |
| `scarps` | Ruptures de pente et bords de falaise, 0 ou 1 | D2 |
| `thermal_inertia` | Inertie thermique THEMIS en J m⁻² K⁻¹ s⁻½ | D1 |
| `loose_soil` | Classe de sol (0 roche, 1 mixte, 2 meuble, 3 dune) | D2 |
| `crism_minerals` | Indice ou classe minéralogique CRISM | D1 |
| `radio_coverage` | Visibilité radio depuis l'habitat ou le rover, 0 ou 1 | D2 |
| `illumination` | Fraction éclairée à l'heure de référence | D2 |
| `return_time` | Temps de retour le plus court vers l'habitat, en s | P3 (calculé à la volée, aussi exportable en couche) |
| `rover_traverse` | Trajet de Perseverance (vecteur) | G1 |
| `ground_images` | Positions des images au sol (vecteur) | G1 |

Ajouter une couche ne demande qu'une entrée dans `site.yaml` et une étape de pipeline, sans toucher au front ni à l'API (ENF-09).

### 5.4 Site fictif

`fixtures/sites/fictif/` est un paquet complet de 2 x 2 km à 2 m, généré par un script de T00 et versionné dans Git (moins de 30 Mo). Il est placé aux coordonnées du centre du cratère Jezero et contient : un plateau limité par une falaise (comme le front du delta), un bord de cratère abrupt, un champ de dunes à faible inertie thermique, un chaos de blocs, deux unités minéralogiques, un habitat et quatre cibles. Toutes les couches du tableau ci-dessus y existent, avec `source.instrument = "SYNTHETIC"`. Le script `tools/validate_site_package.py` valide n'importe quel paquet contre le schéma ; D3 doit produire des paquets qui le passent.

## 6. API et temps réel

Les modèles Pydantic de `packages/core/marswalk_core/schemas.py` sont la source de vérité. T00 exporte le schéma dans `contracts/openapi.json` ; l'intégration continue échoue si l'export diffère du fichier versionné. Le front utilise le client généré par `openapi-typescript` dans `web/src/shared/api/`. Toutes les routes ci-dessous existent dès T00 et renvoient les exemples de `contracts/examples/` tant que la tâche propriétaire ne les a pas implémentées.

| Méthode et chemin | Rôle | Tâche |
| --- | --- | --- |
| `GET /api/health` | État et version | T00 |
| `GET /api/sites`, `GET /api/sites/{site_id}` | Liste des sites et manifeste | A1 |
| `GET /tiles/{site_id}/{layer_id}/{z}/{x}/{y}.{ext}` | Tuiles statiques | A1 |
| `GET /api/sites/{site_id}/query?lon=&lat=` | Valeurs de toutes les couches en un point, avec source, incertitude et temps de retour (EF-07) | A1 |
| `GET /api/sites/{site_id}/hazards?preset=` | Zones interdites et pénalisées en GeoJSON, selon les seuils courants | A2 |
| `GET` et `PUT /api/sites/{site_id}/settings` | Seuils de sécurité, poids du coût, réserve minimale | A2 |
| `GET`, `POST /api/sites/{site_id}/targets` ; `PATCH`, `DELETE /api/targets/{id}` | Cibles et points de passage (EF-04) | A2 |
| `POST /api/sites/{site_id}/plans` | Calcule un plan : variantes, tronçons, profil, budgets, retour garanti (EF-05, EF-06) | A2 |
| `GET /api/plans/{id}`, `PATCH /api/plans/{id}` | Lire un plan, choisir une variante | A2 |
| `GET /api/sites/{site_id}/conditions/current`, `/forecast` | Météo, poussière, dose, météo spatiale (EF-11) | A3 |
| `GET /api/scenarios`, `POST /api/scenarios/{id}/start`, `/stop` | Rejeu d'un scénario | A3 |
| `GET /api/alerts`, `POST /api/alerts/{id}/ack` | Alertes actives et acquittement (EF-08) | A3 |
| `GET /api/time` | UTC, date solaire martienne, sol de mission, heure solaire locale (ENF-11) | A3 |
| `POST /api/eva`, `GET /api/eva/{id}` | Démarrer et lire une sortie | A4 |
| `POST /api/eva/{id}/position`, `/observations`, `/obstacles` | Position, notes, obstacle signalé (recalcul local) | A4 |
| `POST /api/eva/{id}/simulate` | Lancer l'astronaute virtuel (vitesse réglable) | A4 |
| `GET /api/sites/{site_id}/ground-images` | Images au sol en GeoJSON (EF-09) | G1 |
| `GET /api/plans/{id}/export.geojson`, `GET /api/eva/{id}/logbook` | Export et carnet (EF-15) | X1 |

**Objet `Route`** (une variante) : `id`, `variant` (`safest`, `fastest`, `science`), `geometry` (LineString en degrés), `segments` (pour chaque tronçon : départ, arrivée, distance, durée, dénivelés, pente maximale, dose, oxygène et batterie consommés, temps de travail à la cible), `profile` (échantillons tous les 5 m : distance cumulée, position, altitude, pente, temps cumulé), `totals`, `return_check` (`ok`, réserve au retour en %, point de non-retour), `explanation` (raisons par tronçon, par exemple « contourne une pente de 24° »), `warnings` (couches manquantes, marge accrue).

**WebSocket `/ws/eva/{eva_id}`.** Enveloppe commune : `{ "type", "utc", "sol", "lmst", "payload" }`. Types : `telemetry` (position, cap, vitesse, consommables, dose cumulée), `alert` et `alert_cleared` (niveau `info`, `caution` ou `danger`, cause, action conseillée, valeur et seuil), `conditions`, `route_updated` (après un recalcul), `budget` (réserve, temps restant avant le point de non-retour).

**Base de données.** T00 écrit la migration initiale complète : `targets`, `plans`, `routes`, `evas`, `observations`, `alerts`, avec géométries PostGIS en SRID personnalisé Mars 2000. Aucune autre tâche n'ajoute de migration ; un besoin nouveau passe par une demande de changement de contrat.

## 7. Interfaces des bibliothèques Python

T00 crée ces fonctions avec leur signature, leur docstring et un bouchon simple (indiqué entre parenthèses). Les tâches propriétaires remplacent le corps sans changer la signature.

```python
# marswalk_core.site_package (T00, réel dès le départ)
load_site(site_id: str) -> Site
Site.read_layer(layer_id: str, window=None) -> xarray.DataArray   # grille d'analyse
Site.sample(layer_id: str, lon: float, lat: float) -> float | None

# marswalk_core.geodesy (C1 ; bouchon : formule sphérique simple)
distance_m(a: LonLat, b: LonLat) -> float
bearing_deg(a: LonLat, b: LonLat) -> float
to_analysis(site, lon, lat) -> tuple[float, float]
to_lonlat(site, x, y) -> tuple[float, float]

# marswalk_core.marstime (C1 ; bouchon : sol = jours écoulés)
mars_time(utc: datetime, lon_east: float, epoch_utc: datetime) -> MarsTime  # msd, sol, lmst

# marswalk_planner.hazards et cost (P1 ; bouchon : interdit au-delà de 20° de pente)
hazard_masks(site, settings: SafetySettings) -> HazardMasks
hazard_polygons(site, settings) -> FeatureCollection
build_cost_grid(site, settings, conditions: Conditions | None) -> CostGrid
explain_cell(cost_grid, x, y) -> list[CostTerm]

# marswalk_planner.route, order, variants (P2 ; bouchon : ligne droite)
plan_route(cost_grid, waypoints: list[LonLat], options: RouteOptions) -> RouteGeometry
order_targets(cost_grid, start, targets, options) -> list[Target]
plan_variants(site, settings, start, targets, options) -> list[Route]

# marswalk_planner.walk, budget, return_field (P3 ; bouchon : 1 m/s, consommation constante)
walking_speed(slope_deg: float, soil_class: int, suit: SuitModel) -> float
estimate_route(site, geometry, targets, suit, conditions) -> RouteEstimate
return_field(cost_grid, habitat: LonLat, suit) -> ReturnField   # temps de retour depuis chaque case
return_check(estimate, return_field, suit) -> ReturnCheck

# marswalk_conditions (K1 ; bouchon : conditions constantes)
class ConditionsProvider(Protocol):
    def current(self, utc: datetime) -> Conditions: ...
    def forecast(self, utc: datetime, hours: int) -> list[Conditions]: ...
get_provider(mode: Literal["historical", "scenario", "live"], scenario_id: str | None) -> ConditionsProvider
```

## 8. Front : coquille, registre et magasin partagé

**Coquille (T00).** Trois mises en page : `habitat` (grand écran, carte au centre, panneaux latéraux), `tablet` (même contenu, cibles tactiles d'au moins 2 cm soit environ 76 px CSS), `hud` (plein écran à fort contraste). Routes : `/`, `/tablet`, `/hud`, `/3d`.

**Registre.** `web/src/app/registry.ts` liste dès T00 toutes les fonctionnalités, chacune avec un module vide. Chaque fonctionnalité exporte depuis `features/<nom>/index.ts` un objet :

```ts
export const feature: Feature = {
  id: "targets",
  panels: [{ slot: "right", order: 20, component: TargetsPanel }],
  mapLayers: (ctx) => [/* couches deck.gl */],
  mapSources: [/* sources MapLibre */],
  routes: [],
  hudWidgets: [],
};
```

Les emplacements (`slot`) sont fixes : `left`, `right`, `bottom`, `top-banner`, `map-overlay`, `hud-center`, `hud-corner`. Une fonctionnalité n'importe jamais le code interne d'une autre ; elle passe par le magasin partagé ou par l'API.

**Magasin partagé (T00, gelé).** `web/src/shared/store.ts` (Zustand) : `siteId`, `mode`, `layers` (visibilité et opacité par identifiant), `preset`, `selectedTargetId`, `activePlanId`, `activeRouteId`, `hoverDistanceM` (synchronise carte, profil et 3D), `evaId`, `pickMode` (`none`, `query`, `addTarget`). Les données serveur passent par TanStack Query avec les clés définies dans `web/src/shared/queryKeys.ts`.

**Jetons de design (T00).** Palette sûre pour les daltoniens, rouge réservé au danger (ENF-06), trois niveaux d'alerte (`info`, `caution`, `danger`), thème clair à fort contraste pour le plein soleil et thème sombre pour la basse lumière.

**Faux serveur.** `pnpm dev:mock` lance le front avec des gestionnaires MSW qui renvoient `contracts/examples/`, et sert les tuiles du site fictif. Les tâches du front se développent ainsi sans l'API.

## 9. Règles de travail communes

- **Branche :** `task/<ID>-<slug>`, par exemple `task/P2-itineraire`. Une PR par tâche, titrée `[<ID>] <titre>`.
- **Définition de « fini »** pour toutes les tâches : lint, typage (mypy strict en Python, `tsc --noEmit` en TypeScript) et tests verts ; contrôle de propriété vert ; contrat inchangé ; un `README.md` dans le dossier de la tâche ; les critères d'acceptation de la fiche démontrés par un test ou par une capture jointe à la PR.
- **Données :** développer et tester sur `fixtures/sites/fictif/`. Ne jamais versionner de données réelles dans Git.
- **Demande de changement de contrat :** l'agent n'édite pas `contracts/`, `schemas.py`, `store.ts`, `registry.ts` ni la migration. Il écrit `tasks/change-requests/<ID>-<sujet>.md` (champ, raison, effet sur les autres tâches), contourne au mieux dans son périmètre et le signale dans sa PR. La personne ou un agent intégrateur applique les demandes groupées dans une PR `contracts-v2`, puis les branches en cours rebasent.
- **Validation humaine :** les tâches marquées ainsi s'arrêtent sur une PR en brouillon et attendent l'avis de la personne.

## 10. Fiches de tâches

Chaque fiche donne : vague, dépendances, ce que la tâche possède, ce qu'elle livre, ses critères d'acceptation et les exigences couvertes. « Possède » renvoie aux chemins de la section 3.

### T00. Socle, contrats et site fictif

- **Vague :** 0. **Dépend de :** rien. **Possède :** `contracts/`, `config/` (création), `fixtures/`, `packages/core/` sauf `marstime.py` et `geodesy.py`, `api/marswalk_api/main.py`, `db/`, `deps.py`, `web/src/app/`, `web/src/shared/` sauf `marstime.ts` et `geodesy.ts`, `infra/docker-compose.yml`, `.github/`, `tools/`, `tasks/`, `docs/scenario-demo.md`, fichiers racine.
- **Objectif :** rendre possible le travail parallèle de toutes les autres tâches.
- **Livrables :**
  - Monorepo pnpm et uv, avec lint, typage, tests et intégration continue GitHub Actions.
  - Docker Compose : PostGIS 16, API, front ; `make dev` et `make test`.
  - Tout le contenu des sections 3 à 8 : schémas, routes en bouchon, migration complète, interfaces Python en bouchon, coquille du front, registre, magasin, jetons, faux serveur.
  - Le site fictif et `tools/validate_site_package.py`.
  - `tools/check_ownership.py` et `tasks/ownership.yaml`.
  - `docs/scenario-demo.md` : le scénario de démo en dix à quinze étapes (planifier trois cibles, voir les zones dangereuses, comparer les variantes, lancer la sortie, suivre au HUD, éruption solaire simulée, alerte, retour forcé et recalcul vers l'habitat). Chaque étape nomme les tâches qui la rendent possible.
- **Acceptation :** `docker compose up` affiche la carte du site fictif avec au moins une couche ; toutes les routes répondent selon les exemples ; l'export OpenAPI est identique au fichier versionné ; le client TypeScript se génère ; une branche de test qui modifie un fichier hors périmètre fait échouer le contrôle de propriété.
- **Couvre :** socle de toutes les exigences, ENF-03 (règles géographiques), ENF-09 (structure pilotée par configuration).

### C1. Temps martien et géodésie

- **Vague :** 1. **Dépend de :** T00. **Possède :** `packages/core/marswalk_core/marstime.py`, `geodesy.py`, `web/src/shared/marstime.ts`, `geodesy.ts`, et leurs tests.
- **Objectif :** des calculs de temps et de distance martiens identiques en Python et en TypeScript.
- **Livrables :** algorithme Mars24 (Allison et McEwen) pour la date solaire martienne, l'heure solaire locale moyenne et le sol de mission ; distances, caps et conversions entre degrés et système d'analyse avec le rayon martien ; barre d'échelle martienne réutilisable (composant dans `web/src/shared/`). Un fichier de cas de test commun, `packages/core/tests/marstime_vectors.json`, est lu par les deux implémentations.
- **Acceptation :** les cas publiés par le Mars24 de la NASA GISS sont retrouvés à la seconde près ; Python et TypeScript donnent les mêmes résultats sur tous les cas ; une distance de 1° de longitude à l'équateur vaut environ 59,3 km.
- **Couvre :** ENF-11, R3.

### D1. Ingestion et recalage des données réelles de Jezero

- **Vague :** 1. **Dépend de :** T00 et le jeu de données. **Possède :** `pipeline/ingest/`, `pipeline/coreg/`, `config/sites/jezero/`. **Validation humaine.**
- **Objectif :** des rasters réels alignés sur la grille d'analyse de Jezero.
- **Entrées :** les produits bruts dans `data/raw/jezero/` avec un fichier `sources.yaml` (identifiant PDS, URL, date pour chacun) : image et MNT HiRISE (jeu Mars 2020 de l'atterrissage), CTX, MOLA, THEMIS, CRISM, téléchargés surtout depuis Mars Trek.
- **Livrables :** commande `marswalk ingest jezero` qui découpe 5 x 5 km autour du site, reprojette selon R1, recale THEMIS et CRISM sur HiRISE par points d'appui, puis écrit `data/work/jezero/aligned/<layer_id>.tif` et `coreg_report.md` (décalage résiduel mesuré par couche). Un projet QGIS `qgis/jezero.qgz` permet la vérification visuelle. Si le MNT HiRISE ne couvre pas toute l'emprise, le repli CTX ou MOLA est appliqué et noté `degraded`.
- **Acceptation :** les rasters ont tous la même grille ; le décalage résiduel est indiqué pour chaque couche et reste sous 1 pixel de la couche la plus grossière ; la personne valide la superposition dans QGIS.
- **Couvre :** EF-01 (données), ENF-03, ENF-04 (incertitude de recalage), ENF-07.

### D2. Couches dérivées

- **Vague :** 1. **Dépend de :** T00. **Possède :** `pipeline/derived/`.
- **Objectif :** toutes les couches calculées à partir du MNT, de l'imagerie et de THEMIS.
- **Livrables :** commande `marswalk derive <site_id>` qui produit `slope`, `roughness`, `hillshade`, `obstacles` (rugosité et blocs de plus de 0,5 m, avec tampon réglable), `scarps`, `loose_soil` (inertie thermique combinée à la texture HiRISE), `radio_coverage` (visibilité depuis l'habitat et le rover sur le MNT, hauteur d'antenne réglable) et `illumination` (ombres portées pour une heure solaire donnée). Les paramètres viennent de `site.yaml`.
- **Acceptation :** sur le site fictif, la falaise apparaît dans `scarps`, les dunes dans `loose_soil`, et un point caché par le bord du cratère est hors couverture radio ; la pente d'un plan incliné synthétique de 15° est retrouvée à 0,1° près ; le calcul complet tient en moins de 5 minutes sur 5 x 5 km à 1 m.
- **Couvre :** EF-03, sécurité (obstacles, falaises, sol meuble, radio, lumière).

### D3. Paquet de site

- **Vague :** 1. **Dépend de :** T00. **Possède :** `pipeline/package/`.
- **Objectif :** transformer les rasters alignés et dérivés en paquet de site conforme à la section 5.
- **Livrables :** commande `marswalk package <site_id>` qui écrit les COG, les tuiles d'affichage WebP avec la palette de la légende, les tuiles terrain-RGB et le manifeste avec la provenance, puis lance le validateur ; une cible `make site SITE=jezero` enchaîne `ingest`, `derive` et `package`.
- **Acceptation :** le paquet régénéré à partir des sources du site fictif passe le validateur et ressemble au paquet de T00 ; les tuiles s'alignent dans MapLibre avec les COG (une valeur interrogée correspond au pixel affiché) ; la taille est contrôlée et refusée au-delà de 2 Go ; la commande est reproductible.
- **Couvre :** EF-01, EF-02 (données), ENF-01, ENF-03, ENF-04, ENF-09, ENF-10.

### P1. Moteur de risque et grille de coût

- **Vague :** 1. **Dépend de :** T00. **Possède :** `planner/marswalk_planner/cost.py`, `hazards.py`, valeurs par défaut de `config/safety.yaml`.
- **Objectif :** traduire les couches et les conditions en zones interdites, pénalités et coût par case.
- **Livrables :** masques interdits (pente au-delà de 20°, obstacles, dunes actives, tampon de falaise), pénalités (pente de 10 à 20°, sol meuble, hors couverture radio, ombre), fonction `C = w_t · t + w_r · R − w_s · S` de la section 7 des besoins à 2 m ; polygones GeoJSON des zones avec leur cause ; explication des termes de coût d'une case ; marge de sécurité accrue et avertissement si une couche est `missing` ou `degraded`.
- **Acceptation :** construire la grille de 5 x 5 km à 2 m prend moins de 1 s ; changer un seuil change les polygones et la grille ; supprimer `thermal_inertia` du manifeste donne un avertissement et une marge accrue au lieu d'une erreur.
- **Couvre :** EF-03 (seuils), EF-05 (zones interdites), ENF-07, ENF-12.

### P2. Recherche d'itinéraire et variantes

- **Vague :** 1. **Dépend de :** T00 (bouchons de P1 et P3). **Possède :** `planner/marswalk_planner/route.py`, `order.py`, `variants.py`.
- **Objectif :** l'itinéraire sûr entre les points, en moins de 5 s.
- **Livrables :** chemin de coût minimal par tronçon avec `MCP_Geometric` dans une fenêtre élargie autour du tronçon (élargie automatiquement si aucun chemin n'est trouvé) ; lissage qui ne recoupe aucune case interdite ; ordre des cibles optimisé (voyageur de commerce exact jusqu'à 8 cibles) ou imposé ; trois variantes (la plus sûre, la plus rapide, la plus riche en science) par jeux de poids ; cache des tronçons pour ne recalculer que ceux qui changent ; recalcul local depuis une position et un nouvel obstacle.
- **Acceptation :** aucun point du tracé dans une case interdite (test de propriété sur des grilles aléatoires) ; test de performance : cinq cibles sur une grille de 2 500 x 2 500 en moins de 5 s, déplacement d'une cible en moins de 2 s ; les trois variantes diffèrent sur le site fictif.
- **Couvre :** EF-05, ENF-02, section 7 des besoins (étapes 4, 5 et 8).

### P3. Modèle de marche, budgets et retour garanti

- **Vague :** 1. **Dépend de :** T00. **Possède :** `planner/marswalk_planner/walk.py`, `budget.py`, `return_field.py`, valeurs par défaut de `config/suit.yaml`, `docs/science/hypotheses-marche.md`.
- **Objectif :** savoir combien de temps, d'oxygène et de dose coûte chaque tronçon, et garantir le retour.
- **Livrables :** vitesse de type Tobler adaptée à 0,38 g et à une combinaison rigide, paramètres justifiés par les données Apollo et les simulations analogues ; consommation d'oxygène, de batterie et d'eau selon l'effort ; dose par tronçon à partir des conditions ; temps de travail aux cibles ; champ de temps de retour depuis chaque case vers l'habitat ou le rover ; vérification du retour avec 30 % de réserve, point de non-retour et liste des cibles à couper sinon.
- **Acceptation :** vitesse maximale autour de 0 à 5° de descente et décroissante au-delà ; sur le site fictif, un plan trop long est refusé avec la cible à couper nommée ; le champ de retour se calcule en moins de 2 s ; chaque paramètre est sourcé dans `hypotheses-marche.md`.
- **Couvre :** EF-06 (durées), EF-08 (consommables), sécurité (fatigue, consommables, points de repli).

### K1. Conditions martiennes et scénarios

- **Vague :** 1. **Dépend de :** T00. **Possède :** `conditions/`.
- **Objectif :** des conditions du moment et des prévisions, réelles, rejouées ou simulées.
- **Livrables :** import des séries historiques MEDA de Perseverance (température, pression, vent, UV, opacité) et RAD (débit de dose ; Perseverance n'a pas de RAD, on reprend les mesures de Curiosity à Gale, transposées à Jezero et présentées comme telles) depuis le PDS dans un format compact ; client DONKI avec cache local, utilisé seulement en mode `live` ; moteur de scénarios qui rejoue une chronologie accélérée ; le scénario `solar-event` fondé sur un événement réel mesuré par RAD (l'événement de mai 2024 est le meilleur candidat, date et dose à confirmer dans le PDS) ; prévisions simples par climatologie MEDA à l'heure locale.
- **Acceptation :** le mode `historical` renvoie des valeurs MEDA réelles pour un sol donné ; le scénario `solar-event` produit un pic de dose à l'instant prévu, de façon reproductible ; sans réseau, tout fonctionne sauf `live`, qui renvoie la dernière valeur en cache avec sa date.
- **Couvre :** EF-08 (radiation, poussière), EF-11, ENF-01.

### A1. API site, couches et interrogation de point

- **Vague :** 1. **Dépend de :** T00. **Possède :** `api/marswalk_api/routers/sites.py`, `query.py`, `tiles.py`.
- **Livrables :** manifestes des sites, service des tuiles statiques avec en-têtes de cache, interrogation d'un point qui lit toutes les couches COG et renvoie valeur, unité, source, incertitude, statut et temps de retour.
- **Acceptation :** interrogation en moins de 200 ms sur 5 x 5 km ; un point hors emprise renvoie une erreur claire ; une couche `missing` apparaît avec une valeur nulle et son statut.
- **Couvre :** EF-07, ENF-02, ENF-04.

### A2. API cibles, itinéraires et persistance

- **Vague :** 1. **Dépend de :** T00. **Possède :** `api/marswalk_api/routers/targets.py`, `plans.py`, `hazards.py`.
- **Livrables :** CRUD des cibles dans PostGIS (objectif scientifique, mesure prévue, temps de travail) ; réglages de sécurité ; calcul de plan qui appelle `plan_variants`, `estimate_route` et `return_check` ; zones dangereuses en GeoJSON ; grille de coût en mémoire par site et réglages.
- **Acceptation :** déplacer une cible puis recalculer le plan prend moins de 5 s de bout en bout sur 5 x 5 km ; la réponse respecte le schéma `Plan` ; tests d'API sur PostGIS dans Docker.
- **Couvre :** EF-04, EF-05, EF-06 (données), EF-08 (seuils réglables).

### A3. Alertes et temps réel

- **Vague :** 1. **Dépend de :** T00. **Possède :** `api/marswalk_api/routers/alerts.py`, `ws.py`, `conditions.py`, `time.py`.
- **Livrables :** moteur d'alertes qui compare télémétrie, conditions et budgets aux seuils de `safety.yaml` (pente, dose, débit de dose, opacité, réserve, lumière restante, perte radio) ; trois niveaux avec action conseillée ; anti-rebond pour éviter les alertes qui clignotent ; WebSocket selon la section 6 ; routes des conditions, des scénarios et du temps.
- **Acceptation :** lancer le scénario `solar-event` déclenche une alerte `danger` « retour à l'abri » en moins de 1 s ; une alerte s'acquitte en une action ; chaque message porte UTC, sol et heure locale.
- **Couvre :** EF-08, EF-11, ENF-08 (hiérarchie), ENF-11.

### A4. Simulateur de sortie

- **Vague :** 1. **Dépend de :** T00. **Possède :** `api/marswalk_api/routers/eva.py`.
- **Objectif :** faire vivre la démo : un astronaute virtuel qui marche le long du tracé.
- **Livrables :** démarrage d'une sortie sur une variante choisie ; avance simulée à la vitesse du modèle de marche, accélérable ; consommables et dose qui évoluent ; écart volontaire au tracé et obstacle signalé qui déclenchent un recalcul local et un message `route_updated` ; retour forcé vers l'habitat quand une alerte `danger` l'exige.
- **Acceptation :** le scénario de `docs/scenario-demo.md` se déroule en moins de 3 minutes en accéléré ; le recalcul après un obstacle prend moins de 2 s.
- **Couvre :** section 7 des besoins (pendant la sortie), scénario de démo.

### F1. Carte et couches

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/map/`, valeurs de `config/presets.yaml`.
- **Livrables :** carte MapLibre avec deck.gl superposé ; panneau de couches (activer, désactiver, opacité, légende, unité, résolution, date, source) ; préréglages « sécurité », « science », « navigation » ; mode interrogation qui affiche toutes les valeurs du point avec leur source ; barre d'échelle martienne de C1 ; avertissement visible quand une couche est dégradée.
- **Acceptation :** au moins quatre couches réglables indépendamment ; affichage d'une couche en moins de 1 s ; zoom jusqu'à l'échelle d'un rocher sur l'imagerie ; boutons d'au moins 76 px en mode tablette.
- **Couvre :** EF-01, EF-02, EF-03 (affichage), EF-07, ENF-02, ENF-03, ENF-04, ENF-05, ENF-06.

### F2. Cibles et itinéraire

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/targets/`.
- **Livrables :** ajouter, déplacer et supprimer des cibles sur la carte, fiche de cible (objectif, mesure, temps de travail) ; affichage des zones interdites et pénalisées ; tracé des variantes et comparateur (durée, distance, dose, réserve, nombre de cibles) ; choix de la variante ; explication par tronçon ; point de non-retour sur la carte ; recalcul automatique après chaque modification avec indicateur de calcul.
- **Acceptation :** le tracé se met à jour seul après le déplacement d'une cible ; l'astronaute garde la main : aucune variante n'est imposée, et chacune affiche pourquoi elle passe là.
- **Couvre :** EF-04, EF-05 (affichage), ENF-12.

### F3. Profil d'itinéraire

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/profile/`.
- **Livrables :** graphique ECharts de l'altitude et de la pente en fonction de la distance, bandes orange et rouges sur les pentes pénalisées, durée par tronçon, marqueurs des cibles ; survol synchronisé avec la carte et la 3D par `hoverDistanceM`.
- **Acceptation :** survoler le profil déplace un repère sur la carte et inversement ; les totaux du profil égalent ceux de la variante.
- **Couvre :** EF-06.

### F4. Panneau sécurité et conditions

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/safety/`.
- **Livrables :** bandeau d'alertes hiérarchisé avec acquittement en une action ; jauges d'oxygène, de batterie, de dose et de réserve au retour ; compte à rebours avant le point de non-retour et avant le coucher du Soleil ; panneau météo et météo spatiale ; réglage des seuils ; horloge martienne (sol et heure locale avec UTC).
- **Acceptation :** une alerte `danger` reçue par WebSocket s'affiche en moins de 1 s et se traite en deux actions au plus ; la couleur n'est jamais le seul indice (icône et texte aussi).
- **Couvre :** EF-08, EF-11, ENF-05, ENF-06, ENF-08, ENF-11.

### F5. HUD de visière

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/hud/`.
- **Livrables :** vue `/hud` à fort contraste, limitée à cinq informations (cap vers le prochain point, distance, temps restant de sortie, alerte la plus grave, réserve) et rien au centre du champ ; commande vocale (« prochain point », « statut », « retour », « acquitter ») avec Web Speech API, repli local en WebAssembly et repli sur grosses touches ; mêmes données que l'écran d'habitat par WebSocket.
- **Acceptation :** jamais plus de cinq éléments visibles ; lisible sur fond clair et sombre ; une commande vocale ou une touche acquitte une alerte ; fonctionne sans Internet avec le repli.
- **Couvre :** EF-12, ENF-05, ENF-08.

### F6. Vue 3D

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/terrain3d/`.
- **Livrables :** `TerrainLayer` de deck.gl alimentée par `terrain_rgb`, drapée de l'imagerie ou de n'importe quelle couche ; tracé et cibles en 3D ; survol de l'itinéraire avec une caméra qui suit le tracé, pause et vitesse ; repère synchronisé avec le profil.
- **Acceptation :** le survol complet se lance d'un clic et reste fluide (au moins 30 images par seconde sur un portable courant) ; l'exagération verticale est réglable et indiquée.
- **Couvre :** EF-10.

### F7. Hors ligne

- **Vague :** 1. **Dépend de :** T00. **Possède :** `web/src/features/offline/`, configuration Workbox dans ce dossier (branchée par la coquille de T00).
- **Livrables :** PWA installable ; préchargement du paquet de site (tuiles, manifeste, vecteurs) avec barre de progression et taille annoncée ; indicateur de connexion ; file d'attente des modifications (cibles, observations) rejouée au retour du serveur.
- **Acceptation :** après chargement, couper le réseau et l'API : la carte, les couches, le dernier plan et le HUD restent utilisables ; les observations saisies hors ligne arrivent au serveur au retour.
- **Couvre :** ENF-01, ENF-10.

### S1. Objectif scientifique et cibles

- **Vague :** 1. **Dépend de :** T00 (et D1 pour placer les cibles sur Jezero). **Possède :** `docs/science/` (sauf `hypotheses-marche.md`), `config/sites/jezero/targets-seed.geojson`. **Validation humaine.**
- **Livrables :** une page qui justifie le site (delta de Jezero, argiles et carbonates, roches ignées à olivine du plancher, ce que Perseverance y a mesuré et prélevé, pourquoi un humain y apporterait plus qu'un rover) ; trois à cinq cibles avec objectif, mesure prévue et temps de travail, chacune appuyée par une couche (CRISM, imagerie, inertie thermique) et une source citée ; justification des seuils de sécurité (20°, 30 %, taille des blocs) pour le pitch.
- **Acceptation :** chaque affirmation cite une source NASA ou une publication ; les cibles se chargent dans l'application ; la personne valide le contenu.
- **Couvre :** critère « objectif scientifique » du défi, ENF-04.

### G1. Images au sol

- **Vague :** 1. **Dépend de :** T00. **Possède :** `pipeline/ground_images/`, `api/marswalk_api/routers/ground_images.py`, `web/src/features/ground-images/`.
- **Livrables :** index des images Mastcam-Z et Navcam de Perseverance prises dans l'emprise, avec position du rover au sol de prise de vue (données de traverse), vignettes et lien vers l'image complète ; trajet du rover en vecteur ; icônes sur la carte et visionneuse ; images les plus proches proposées sur la fiche d'une cible.
- **Acceptation :** au moins vingt images positionnées sur Jezero ; chaque image affiche sol, instrument et identifiant.
- **Couvre :** EF-09, ENF-04.

### X1. Export et carnet de terrain (bonus, coût faible)

- **Vague :** 1. **Dépend de :** T00. **Possède :** `api/marswalk_api/routers/export.py`, `web/src/features/export/`.
- **Livrables :** export du plan en GeoJSON et en PDF imprimable (carte, profil, tableau des tronçons) ; carnet de sortie horodaté en sol et heure locale, avec position, notes et photos.
- **Acceptation :** le GeoJSON exporté se rouvre dans QGIS au bon endroit ; le carnet d'une sortie simulée liste toutes ses observations.
- **Couvre :** EF-15.

### I1. Bascule sur Jezero et calibration

- **Vague :** 2. **Dépend de :** D1 validée, D2, D3, P1, P2, P3. **Possède :** `config/sites/jezero/` après D1, `config/safety.yaml` et `config/suit.yaml` pour l'ajustement, `docs/calibration.md`.
- **Livrables :** paquet de Jezero produit par `make site SITE=jezero` ; site par défaut basculé sur Jezero ; seuils et poids ajustés pour que les variantes soient crédibles sur le vrai relief ; mesures de performance sur la vraie grille ; correctifs nécessaires transmis aux tâches concernées ou faits dans une PR étiquetée `fix/<ID>`.
- **Acceptation :** toutes les mesures d'ENF-02 tiennent sur Jezero ; les étapes du scénario de démo passent sur Jezero.
- **Couvre :** ENF-02, ENF-10 sur données réelles.

### I2. Tests de bout en bout du scénario de démo

- **Vague :** 3. **Dépend de :** toutes les tâches M et S, I1. **Possède :** `e2e/`.
- **Livrables :** tests Playwright qui rejouent `docs/scenario-demo.md` sur les vues habitat, tablette et HUD ; test hors ligne ; contrôle d'accessibilité automatique (axe) sur les trois vues ; rapport des écarts.
- **Acceptation :** le scénario complet passe trois fois de suite dans l'intégration continue. Le gel des fonctionnalités est posé à la fusion de cette tâche.
- **Couvre :** vérification de toutes les exigences M et S.

### L1. Déploiement et mode démo

- **Vague :** 4. **Dépend de :** I2. **Possède :** `infra/deploy/`, workflows de déploiement.
- **Livrables :** front sur Vercel, API sur Fly.io avec PostGIS, paquet de site sur Cloudflare R2 ; commande de réinitialisation de la démo (cibles d'exemple, plan prêt, scénario prêt) ; page d'accueil qui explique en une phrase quoi essayer.
- **Acceptation :** la démo en ligne déroule le scénario ; une réinitialisation la remet à zéro en moins de 30 s.

### L2. Pitch, vidéo et dossier de soumission

- **Vague :** 4. **Dépend de :** I2 (et S1). **Possède :** `docs/pitch/`, `README.md` racine (section présentation). **Validation humaine.**
- **Livrables :** script du pitch de 3 minutes (problème, démo, sécurité, science) ; plan de la vidéo et sous-titres ; liste des sources NASA utilisées ; texte de soumission selon le règlement.
- **Acceptation :** le pitch tient en 3 minutes à voix haute ; chaque donnée NASA citée apparaît dans l'application.

### Bonus après le jalon J2

- **X2. Générateur pour n'importe quel site (EF-14).** Possède `pipeline/generator/`. Saisie de coordonnées, téléchargement automatique des tuiles CTX et MOLA de Mars Trek, puis `derive` et `package` avec la marge accrue d'ENF-07.
- **X3. Binôme ou rover (EF-13).** Possède `planner/marswalk_planner/team.py` et `web/src/features/team/`. Deux tracés coordonnés ou un tronçon en rover pressurisé avec sa vitesse ; demande sans doute un changement de contrat pour le schéma `Plan`.
- **X4. Démo WebXR sur casque Quest.** Possède `web/src/features/xr/`. Réutilise le HUD dans une session WebXR.

## 11. Texte de lancement d'un agent

À coller avant la fiche de la tâche :

> Tu travailles sur le monorepo Marswalk. Lis d'abord `taches-agents.md` sections 3 à 9, `docs/scenario-demo.md` et le `README.md` racine. Tu réalises uniquement la tâche dont la fiche suit, sur la branche `task/<ID>-<slug>` créée depuis `main`. Tu ne modifies que les chemins que ta fiche te donne ; les contrats (`contracts/`, `schemas.py`, `store.ts`, `registry.ts`, la migration) sont gelés, et tout besoin de changement passe par `tasks/change-requests/`. Développe et teste sur le site fictif. Avant d'ouvrir la PR, rebase sur `main`, lance `make test`, vérifie chaque critère d'acceptation et décris dans la PR comment chacun est démontré. Si ta fiche porte la mention « validation humaine », ouvre la PR en brouillon et attends.

## 12. Couverture des exigences

| Exigence | Tâches |
| --- | --- |
| EF-01 carte de base | D1, D3, F1 |
| EF-02 trois couches et opacité | D1, D3, F1 |
| EF-03 pente, rugosité, ombrage | D2, P1, F1 |
| EF-04 cibles | A2, F2, S1 |
| EF-05 itinéraire sûr en moins de 5 s | P1, P2, A2, F2 |
| EF-06 profil | P3, A2, F3 |
| EF-07 interrogation de point | A1, F1 |
| EF-08 alertes | P3, K1, A3, F4 |
| EF-09 images au sol | G1 |
| EF-10 vue 3D | D3, F6 |
| EF-11 conditions et prévisions | K1, A3, F4 |
| EF-12 HUD | F5 |
| EF-13 binôme ou rover | X3 (bonus) |
| EF-14 générateur de site | X2 (bonus) |
| EF-15 export et carnet | X1 |
| ENF-01 hors ligne | D3, K1, F7 |
| ENF-02 latence | P1, P2, A1, A2, F1, I1 |
| ENF-03 précision géographique | T00, D1, D3, C1 |
| ENF-04 traçabilité | D1, D3, A1, F1, S1, G1 |
| ENF-05 utilisable en combinaison | T00, F1, F4, F5 |
| ENF-06 lisibilité | T00, F1, F4, I2 |
| ENF-07 dégradation gracieuse | D1, P1, F1 |
| ENF-08 charge cognitive | A3, F4, F5 |
| ENF-09 extensibilité | T00, D3 |
| ENF-10 taille du paquet | D3, F7, I1 |
| ENF-11 temps martien | C1, A3, F4 |
| ENF-12 conseil et explication | P1, F2 |
| Sécurité : retour garanti, point de non-retour, temps de retour | P3, F2, F4 |
| Sécurité : radio, lumière, falaises, sol meuble | D2, P1 |
| Objectif scientifique | S1 |
| Scénario de démo et éruption solaire | T00, K1, A3, A4, I2 |
