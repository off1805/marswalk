# Tests C1 — Temps martien et géodésie

## Fonctionnalités implémentées

### Python : `packages/core/marswalk_core/marstime.py`

**`mars_time(utc, lon_east, epoch_utc) → MarsTime`** — algorithme Mars24 complet (Allison & McEwen 2000).

Champs calculés : `msd`, `sol`, `lmst`, `lmst_hours`, `ltst`, `ls_deg`.

### Python : `packages/core/marswalk_core/geodesy.py`

- **`distance_m(a, b)`** — distance orthodromique haversine sur la sphère Mars 2000.
- **`bearing_deg(a, b)`** — cap initial, degrés depuis le nord, [0, 360).
- **`to_analysis(site, lon, lat)`** — conversion degrés → (x, y) en mètres dans le système eqc du site.
- **`to_lonlat(site, x, y)`** — conversion inverse.

### TypeScript : `web/src/shared/marstime.ts`

Miroir exact de l'implémentation Python. Exporte les mêmes fonctions sous forme camelCase :
`marsTime`, `marsSolDate`, `mstHours`, `deltaJ2000Tt`, `ls`, `marsMeanAnomaly`, `eotHours`, `pbs`, …

### TypeScript : `web/src/shared/geodesy.ts`

Déjà fourni par T00. Fonctions : `distanceM`, `bearingDeg`, `metersPerPixel`. Rayon Mars 2000 (3 396 190 m).

### TypeScript : `web/src/shared/geodesy-scale-bar.tsx`

**`<MarsScaleBar zoom lat maxWidthPx />`** — composant React de barre d'échelle martienne.

Exporte aussi **`computeScaleBar(zoom, lat, maxWidthPx)`** utilisable sans React (tests, canevas).

- Paliers affichables : 10 m, 20 m, 50 m, 100 m, 200 m, 500 m, 1 km, 2 km, 5 km, 10 km, 20 km, 50 km.
- Largeur calculée via `metersPerPixel` du rayon martien — jamais via MapLibre ou Turf (règle R3).
- N'utilise jamais la barre d'échelle native de MapLibre.
- Accessible : `role="img"` et `aria-label` avec la distance réelle.

## Algorithme Mars24

L'implémentation suit exactement l'algorithme publié par la NASA GISS :

| Étape | Description |
|-------|-------------|
| A-1 → A-2 | Unix timestamp → Jour Julien UT |
| A-4 | TT − UTC via table IERS de leap seconds (1972–2017) |
| A-5 → A-6 | JDTT et ΔtJ2000 |
| B-1 | Anomalie moyenne `M = 19.3871° + 0.52402073° Δt` |
| B-2 | Fictitious Mean Sun `αFMS = 270.3871° + 0.524038496° Δt` |
| B-3 | Perturbateurs PBS (7 termes de Fourier) |
| B-4 | Équation du centre `ν − M` |
| B-5 | Longitude solaire `Ls = αFMS + (ν − M)` |
| C-1 | Équation du temps EOT en degrés → heures |
| C-2 | Mean Solar Time (Airy Mean Time) |
| C-3 | LMST = MST + lon_east / 15 |
| C-4 | LTST = LMST + EOT / 15 |

### Leap seconds

La conversion TT − UTC utilise la table complète IERS (1972 – 2017-01-01). La valeur dynamique retrouve automatiquement 64.184 s pour les dates de l'an 2000 (exemple 1 NASA GISS) et 69.184 s pour les dates post-2017.

### Convention de longitude

Le projet utilise des **degrés Est** (convention R2). La NASA GISS utilise des **degrés Ouest** dans ses formules :  
`LMST = MST − Λ_west / 15 = MST + lon_east / 15`

## Hypothèses scientifiques

- **Rayon** : 3 396 190 m (sphère Mars 2000, IAU_2015:49900). Utilisé dans toutes les formules de distance et de projection.
- **1 sol** = 1,0274912517 jours terrestres = 88 775,244 s.
- **Sol de mission** : 1 pendant le premier sol terrestre après `epoch_utc`; s'incrémente au bout de chaque intervalle de 88 775,244 s. Les décimales sont importantes — le sol 2 commence à 88 775,244 s, pas 88 775,000 s.
- **Leap seconds** : table IERS figée à 2017. Aucun ajout jusqu'en novembre 2026 (IERS Bulletin C 67).

## Paramètres et unités

| Paramètre | Unité | Description |
|-----------|-------|-------------|
| `msd` | sols (continu) | Mars Sol Date |
| `sol` | entier ≥ 1 | Sol de mission depuis `epoch_utc` |
| `lmst` | HH:MM:SS | Heure solaire moyenne locale |
| `lmst_hours` | heures [0, 24) | Même valeur en décimal |
| `ltst` | HH:MM:SS | Heure solaire vraie locale |
| `ls_deg` | degrés [0, 360) | Longitude solaire |
| `lon_east` | degrés Est | Longitude du site (convention R2) |
| distances | mètres | Toujours rayon Mars 2000 |

## Vecteurs de test partagés Python-TypeScript

Le fichier `packages/core/tests/c1/marstime_vectors.json` contient 13 vecteurs couvrant :

| Catégorie | Vecteurs |
|-----------|----------|
| Références NASA GISS | 2 (cas 1 et cas 2 publiés) |
| Longitudes variées | 4 (Jezero +77.58°, -100°, ±180°) |
| Années bissextiles terrestres | 1 (2000-02-29) |
| Frontière de sol | 1 (2026-11-02T00:39:36Z) |
| LMST dans [0, 24) | 2 (extrêmes ±179.99°) |
| Parité inter-langages | 1 (calcul identique Python/TS) |

## Choix techniques

- Les fonctions auxiliaires privées de `marstime.py` (`_delta_j2000_tt`, `_ls`, etc.) sont exportées pour être testables unitairement sans avoir à traiter une `MarsTime` complète.
- En TypeScript, les mêmes fonctions sont exportées nommément.
- Le composant `MarsScaleBar` est entièrement compatible avec React 19.
- La table de leap seconds est codée en dur (pas de dépendance réseau). Elle couvre 1972–2017 et reste valide jusqu'au prochain leap second éventuel.

## Limites connues

- L'équation du temps donne LTST avec une précision de ~1–2 s. Acceptable pour l'affichage mais insuffisant pour une navigation de précision en degrés (non requis).
- Les coefficients sont ceux du tableau de l'algorithme NASA GISS de novembre 2026 ; des révisions ultérieures de l'algorithme pourraient modifier les constantes.
- Le composant `MarsScaleBar` requiert React et ne fonctionne pas dans des contextes purement HTML statiques.

## Exemples d'utilisation

### Python

```python
from datetime import UTC, datetime
from marswalk_core.marstime import mars_time
from marswalk_core.site_package import load_site

site = load_site("fictif")
epoch = site.manifest.mission_epoch_utc
now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)

mt = mars_time(now, lon_east=site.manifest.habitat.lon, epoch_utc=epoch)
print(f"Sol {mt.sol}, LMST {mt.lmst}, Ls {mt.ls_deg:.1f}°")
# → Sol 14, LMST 17:46:22, Ls 15.9°
```

```python
from marswalk_core.geodesy import distance_m, to_analysis, to_lonlat
from marswalk_core.schemas import LonLat

d = distance_m(LonLat(0, 0), LonLat(1, 0))
print(f"1° à l'équateur = {d:.0f} m")  # → 59 274 m
```

### TypeScript

```typescript
import { marsTime } from "@/shared/marstime";
import { distanceM } from "@/shared/geodesy";
import { MarsScaleBar } from "@/shared/geodesy-scale-bar";

// Heure martienne
const mt = marsTime(new Date(), 77.58, new Date("2026-11-01T00:00:00Z"));
console.log(`Sol ${mt.sol}, LMST ${mt.lmst}`);

// Distance
const d = distanceM([0, 0], [1, 0]);
console.log(`1° = ${d.toFixed(0)} m`);  // → 59 274 m

// Composant barre d'échelle (JSX)
// <MarsScaleBar zoom={14} lat={18.38} maxWidthPx={200} />
```

## Commandes de test

```bash
# Python — C1 uniquement
uv run pytest packages/core/tests/c1/ -v

# Python — suite complète
uv run pytest

# TypeScript (depuis la racine)
npx pnpm test

# Lint + typage Python
uv run ruff check packages/core/marswalk_core/marstime.py packages/core/marswalk_core/geodesy.py packages/core/tests/c1/
uv run mypy packages/core/marswalk_core/marstime.py packages/core/marswalk_core/geodesy.py packages/core/tests/c1/
```

## Références

- Allison, M. et McEwen, M. (2000). *A post-Pathfinder evaluation of areocentric solar coordinates with improved timing recipes for Mars seasonal/diurnal climate studies*. Planetary and Space Science, 48(2–3), 215–235.
- NASA GISS Mars24 Sunclock — Algorithm and Worked Examples : https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
- IERS Bulletin C 67 (leap seconds) : https://www.iers.org/IERS/EN/Publications/Bulletins/bulletins.html
