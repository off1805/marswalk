# D2_REPORT — Couches dérivées (Derived Layers)

**Date :** 2026-11-15
**Site :** Jezero Crater (Perseverance, Mars 2020)
**Statut :** ✅ VALIDÉ — 8/8 couches produites, 45/45 tests passés

---

## 1. Fichiers créés et modifiés

### Modules produits

| Fichier | Rôle |
|---------|------|
| `pipeline/marswalk_pipeline/derived/__init__.py` | API publique : `run_derive()`, utilitaires I/O |
| `pipeline/marswalk_pipeline/derived/_cli.py` | CLI : `python -m marswalk_pipeline.derived <site_id>` |
| `pipeline/marswalk_pipeline/derived/__main__.py` | Point d'entrée `python -m ...` |
| `pipeline/marswalk_pipeline/derived/slope.py` | Calcul pente |
| `pipeline/marswalk_pipeline/derived/roughness.py` | Calcul rugosité |
| `pipeline/marswalk_pipeline/derived/hillshade.py` | Calcul ombrage |
| `pipeline/marswalk_pipeline/derived/obstacles.py` | Masque obstacles |
| `pipeline/marswalk_pipeline/derived/scarps.py` | Masque ruptures de pente |
| `pipeline/marswalk_pipeline/derived/loose_soil.py` | Classification sol |
| `pipeline/marswalk_pipeline/derived/radio_coverage.py` | Viewshed radio |
| `pipeline/marswalk_pipeline/derived/illumination.py` | Ombres solaires |

### Tests produits

| Fichier | Contenu |
|---------|---------|
| `pipeline/tests/d2/__init__.py` | Marqueur de paquet |
| `pipeline/tests/d2/conftest.py` | Fixtures synthétiques réutilisables |
| `pipeline/tests/d2/test_slope.py` | 5 tests pente |
| `pipeline/tests/d2/test_roughness.py` | 5 tests rugosité |
| `pipeline/tests/d2/test_hillshade.py` | 4 tests hillshade |
| `pipeline/tests/d2/test_obstacles.py` | 5 tests obstacles |
| `pipeline/tests/d2/test_scarps.py` | 5 tests scarps |
| `pipeline/tests/d2/test_loose_soil.py` | 5 tests loose_soil |
| `pipeline/tests/d2/test_radio_coverage.py` | 5 tests viewshed |
| `pipeline/tests/d2/test_illumination.py` | 4 tests illumination |
| `pipeline/tests/d2/test_integration.py` | 7 tests intégration sur site fictif |

### Sorties de données (hors Git, dans `data/`)

```
data/work/jezero/derived/
├── slope.tif
├── roughness.tif
├── hillshade.tif
├── obstacles.tif
├── scarps.tif
├── loose_soil.tif
├── radio_coverage.tif
└── illumination.tif
```

---

## 2. Couches dérivées implémentées

Toutes les 8 couches spécifiées dans `taches-agents.md` (fiche D2) sont produites.

| `id` | Titre | Type | Unité | Plage Jezero |
|------|-------|------|-------|--------------|
| `slope` | Pente | derived | deg | [0.00, 75.27] |
| `roughness` | Rugosité | derived | m | [0.00, 6.44] |
| `hillshade` | Ombrage | derived | DN | [0.00, 255.00] |
| `obstacles` | Obstacles | derived | binaire | {0, 1} |
| `scarps` | Ruptures de pente | derived | binaire | {0, 1} |
| `loose_soil` | Classe de sol | derived | classe | {0, 1, 2, 3} |
| `radio_coverage` | Couverture radio | derived | binaire | {0, 1} |
| `illumination` | Éclairement | derived | binaire | {0, 1} |

---

## 3. Données sources utilisées

| Couche dérivée | Source D1 | Notes |
|----------------|-----------|-------|
| `slope`, `roughness`, `hillshade`, `obstacles`, `scarps`, `illumination` | `dem.tif` (HiRISE DTM 1m) | Source principale |
| `radio_coverage` | `dem.tif` | Viewshed depuis position habitat (site.yaml) |
| `loose_soil` | `thermal_inertia.tif` + `hirise_vis.tif` | TI pour les seuils TIU, HiRISE pour la texture |

`crism_minerals.tif` n'est **pas** utilisé pour `loose_soil` : son origine est décalée de 8m/-5m (coreg D1) et son CRS d'origine légèrement différent de `dem.tif`. La combinaison sans rééchantillonnage introduirait un biais spatial non justifié pour ce paramètre.

---

## 4. Algorithmes et paramètres

### `slope` — Pente en degrés
```
dz/dy, dz/dx = np.gradient(dem, resolution_m)
slope = degrees(arctan(sqrt(dz_dx² + dz_dy²)))
```
Gradient central via `np.gradient`. Pixels nodata → nodata propagé.

### `roughness` — Rugosité (écart-type local)
```
Fenêtre win = round(roughness_window_m / resolution_m), arrondie à impaire
σ² = E[x²] - E[x]²  via scipy.ndimage.uniform_filter
σ = sqrt(max(σ², 0))
```
Paramètre : `roughness_window_m = 10.0` → fenêtre 11×11 px sur Jezero.
Propagation nodata : toute fenêtre contenant un pixel nodata → nodata.

### `hillshade` — Ombrage Lambert
```
dz/dx, dz/dy = np.gradient(dem, resolution_m)
n_z = 1 / sqrt(dz_dx² + dz_dy² + 1)
sun_zen = radians(90 - sun_altitude_deg)
sun_az  = radians(360 - sun_azimuth_deg + 90)   # cartographique → mathématique
H = 255 * max(0, cos(zen)*n_z + sin(zen)*(cos(az)*(-dzdx) + sin(az)*(-dzdy)))
```
Paramètres Jezero : `sun_azimuth_deg=90` (Est), `sun_altitude_deg=20`.

### `obstacles` — Masque obstacles avec tampon
```
1. rough > obstacle_roughness_threshold_m → 1
2. binary_dilation(disk radius = obstacle_buffer_m / resolution_m)
```
Paramètres : `obstacle_roughness_threshold_m=0.4`, `obstacle_buffer_m=2.0`.

### `scarps` — Ruptures de pente avec tampon
```
1. slope > scarp_threshold_deg → 1
2. binary_dilation(disk radius = scarp_buffer_m / resolution_m)
```
Paramètres : `scarp_threshold_deg=30.0`, `scarp_buffer_m=10.0`.

### `loose_soil` — Classification sol (4 classes)
```
texture = écart-type local de hirise_vis (fenêtre texture_window_px×px)
si TI < ti_dune ET texture < texture_dune_threshold → 3 (dune)
si TI < ti_loose → 2 (meuble)
si TI < ti_mixed → 1 (mixte)
sinon → 0 (roche)
```
Paramètres par défaut (configurables dans `site.yaml`) :
- `ti_dune_threshold=170` TIU (J m⁻² K⁻¹ s⁻½)
- `ti_loose_threshold=200` TIU
- `ti_mixed_threshold=270` TIU
- `texture_window_px=5`, `texture_dune_threshold=5.0` DN

Distribution Jezero : roche 3.2%, mixte 57.3%, meuble 36.2%, dune 3.3%.

### `radio_coverage` — Viewshed radial (R2V)
```
N_ANGLES=3600 directions angulaires autour de l'habitat
Pour chaque rayon, marche pixel par pixel en maintenant max_angle_élévation
pixel visible si angle_élévation(pixel) ≥ max_angle_élévation_courant
```
Algorithme vectorisé : tous les angles traités en parallèle à chaque pas de distance.
Paramètres : `antenna_height_m=3.0`, hauteur œil cible=1.8m.

Position de l'habitat : lue depuis `habitat: {x, y}` dans `site.yaml` (coordonnées
absolues dans le CRS d'analyse EQC en mètres). Si la position est hors grille
(valeur placeholder avant calibration I1), fallback sur le centre géométrique.

### `illumination` — Ombres portées (shadow casting)
```
Algorithme d'élévation normalisée :
  norm_elev(c) = dem(c) + sun_slope × dist_from_sunny_edge(c)
  sun_slope = tan(sun_altitude_deg)
Scan depuis le bord ensoleillé → pixel en ombre si norm_elev < max(norm_elev précédent)
```
Axe principal déterminé par la composante dominante de la direction solaire.
Interpolation bilinéaire pour les rayons obliques.
Paramètres : `sun_azimuth_deg=90`, `sun_altitude_deg=20`.

---

## 5. Formats et métadonnées des sorties

Toutes les couches dérivées :
- **Format** : GeoTIFF, 1 bande
- **dtype** : Float32
- **NoData** : -9999.0
- **CRS** : `+proj=eqc +lat_ts=18.4446 +lon_0=77.4502 +R=3396190 +units=m +no_defs` (identique à `dem.tif`)
- **Dimensions** : 5000×5000 px
- **Résolution** : 1.0 m/px
- **Transform** : identique à `dem.tif` (c=-2500.0, f=1095798.09)

Les couches binaires (obstacles, scarps, radio_coverage, illumination) ont des valeurs
0.0 et 1.0 encodées en Float32 pour la cohérence avec l'interface D3/P1.

---

## 6. Tests exécutés et résultats

### Tests D2

```
pipeline/tests/d2/ — 45/45 passés en 6.47s
  test_hillshade.py     ....  (4 tests)
  test_illumination.py  ....  (4 tests)
  test_integration.py   .......  (7 tests)
  test_loose_soil.py    .....  (5 tests)
  test_obstacles.py     .....  (5 tests)
  test_radio_coverage.py .....  (5 tests)
  test_roughness.py     .....  (5 tests)
  test_scarps.py        .....  (5 tests)
  test_slope.py         .....  (5 tests)
```

Critères d'acceptation couverts par les tests :
- ✅ Plan incliné synthétique 15° → pente retrouvée à 0.0001° (tolérance spec 0.1°)
- ✅ DEM plat → slope=0, roughness=0, hillshade uniforme, tout visible
- ✅ Nodata propagé sur toutes les couches
- ✅ Couches binaires : seules valeurs 0.0, 1.0, nodata
- ✅ Toutes les couches ont la même grille que `dem.tif`
- ✅ loose_soil : 4 classes détectées sur données synthétiques
- ✅ Obstacle derrière une colline → non visible (viewshed)
- ✅ run_derive("fictif") produit 8/8 couches en < 5 min (2.6s effectif)

### Non-régression D1

```
pipeline/tests/d1/ — 62/62 passés, 2 skipped en 86.87s
  (Les 2 skipped sont des tests sur données Jezero réelles absentes de Git — attendu)
```

### Données réelles Jezero

```
run_derive("jezero") — 8/8 couches produites en 33.7s (< 5 min spec)
```

---

## 7. Limites connues

### 7.1 Position de l'habitat non calibrée

`site.yaml` Jezero contient `habitat: {x: 0, y: 0}` avec la note `# à calibrer par I1`.
Ces coordonnées (mètres absolus dans le CRS EQC) correspondent à l'équateur de Mars,
hors de la grille Jezero. Le code détecte ce cas (position hors grille) et utilise le
centre géométrique de la grille comme fallback. **La calibration de la position réelle
de l'habitat relève de I1.**

### 7.2 Couverture radio très faible sur données réelles

Le viewshed depuis le centre de la grille Jezero donne ~2.9% de pixels visibles (avant
fix) et varie selon la position de l'habitat. Cela est physiquement cohérent avec le
terrain accidenté du delta fluvial de Jezero (variations d'altitude de 200m sur 5km).
Le paramètre `antenna_height_m=3.0` est conservateur ; une valeur de 10–20m (mât relais)
donnerait une couverture plus large. **La calibration relève de I1.**

### 7.3 Obstacles très nombreux sur données HiRISE réelles

Le seuil `obstacle_roughness_threshold_m=0.4` (blocs > 0.4m) sur le DEM HiRISE réel à
1m/px donne ~37% d'obstacles avant tampon, dilatable à ~99% avec `obstacle_buffer_m=2m`.
Le delta de Jezero est effectivement très chaotique (blocs, rochers, escarpements), mais
ce seuil et ce buffer seront à ajuster pour la planification opérationnelle via I1.

### 7.4 Seuils `loose_soil` non validés par des sources primaires

Les seuils TI (170/200/270 TIU) sont issus de la littérature THEMIS/Mars générale.
Leur ajustement pour Jezero spécifiquement relève de S1 (objectif scientifique).
Ils sont configurables dans `site.yaml` via la section `derive:`.

### 7.5 `crism_minerals` non utilisé dans `loose_soil`

La grille CRISM est décalée de 8m/-5m (coreg D1, 2 tie-points faibles). Utiliser ce
raster sans rééchantillonnage sur la grille DEM introduirait un biais spatial. L'intégration
CRISM dans loose_soil (ou dans une couche minéralogique séparée) pourrait être envisagée
après correction du décalage CRISM en I1.

### 7.6 `illumination` : angle solaire fixe

L'illumination est calculée pour un angle solaire fixe (`sun_azimuth_deg=90`,
`sun_altitude_deg=20`). Une illumination dynamique (fonction du sol et de l'heure
locale martienne) est hors scope D2 et relève de K1/A3.

---

## 8. Interventions humaines nécessaires

| Priorité | Action | Responsable |
|----------|--------|-------------|
| I1 | Calibrer la position de l'habitat (`habitat: {x, y}` en mètres dans le CRS d'analyse) | I1 |
| I1 | Ajuster `obstacle_roughness_threshold_m` et `obstacle_buffer_m` pour Jezero | I1 |
| I1 | Ajuster `antenna_height_m` selon l'infrastructure réelle | I1 |
| S1 | Valider les seuils TI de `loose_soil` par des sources THEMIS Jezero | S1 |
| I1 | Vérifier visuellement les couches dérivées dans QGIS | I1 |

---

## 9. Statut de validation D2

| Critère | Statut |
|---------|--------|
| 8/8 couches spécifiées produites | ✅ |
| Même grille que `dem.tif` (5000×5000, 1m/px, CRS EQC) | ✅ |
| Paramètres lus depuis `site.yaml` | ✅ |
| NoData géré sur toutes les couches | ✅ |
| Couches binaires : valeurs 0.0/1.0 uniquement | ✅ |
| Plan incliné 15° → pente à 0.1° près | ✅ (0.0001°) |
| Calcul complet < 5 min sur 5×5 km à 1m | ✅ (33.7s) |
| 45/45 tests D2 passés | ✅ |
| 62/62 tests D1 non-régression passés | ✅ |
| CLI `python -m marswalk_pipeline.derived <site_id>` | ✅ |
| Résultats reproductibles | ✅ (déterministe, numpy/scipy) |
| Données brutes `data/raw/` non modifiées | ✅ |
| Traitements D0/D1 non modifiés | ✅ |

**D2 est VALIDÉ pour le passage à D3.**

La position de l'habitat et les seuils de calibration seront finalisés en I1.

---

*Rapport généré par l'agent D2 — 2026-11-15*
