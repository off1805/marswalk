# Tests P1 — Moteur de risque et grille de coût

## Organisation

| Fichier | Couverture |
|---------|-----------|
| `conftest.py` | Fixtures partagées : `fictif_site`, `standard_settings`, `prudent_settings`, `make_site()`, `make_layers()` |
| `test_slopes.py` | Règles de pente à 9°, 10°, 15°, 20°, 21°. Effet du seuil sur les masques, les polygones et la grille. |
| `test_forbidden_causes.py` | Obstacles, dunes actives, tampon de falaise. Polygones GeoJSON. |
| `test_penalized_causes.py` | Couverture radio, ombres, sol meuble, rugosité. |
| `test_missing_layers.py` | Couches manquantes, dégradées. Marge de sécurité accrue, avertissements. |
| `test_cost_grid.py` | Formule C = w_t·t + w_r·R − w_s·S. Poids, NaN, cohérence, conditions. |
| `test_explain_cell.py` | Décomposition du coût d'une cellule. Cohérence avec le coût réel. |
| `test_consistency.py` | Cohérence entre masques, polygones et grille. Effet des préréglages. |
| `test_performance.py` | Benchmarks : 1000×1000 et simulation 2500×2500. |

---

## Hypothèses scientifiques et choix de conception

### Seuils de sécurité

Les seuils ci-dessous sont ceux du préréglage `standard` de `config/safety.yaml`.
Ils constituent des **hypothèses de conception** : la NASA n'a pas publié de normes
définitives pour les sorties humaines sur Mars.

| Paramètre | Valeur standard | Valeur prudente | Justification |
|-----------|----------------|-----------------|---------------|
| `max_slope_deg` | 20° | 15° | Analogie avec les normes EVA lunaires (Apollo, pente max ~20°). Sur Mars, la gravité plus faible (0,38 g) permettrait théoriquement plus, mais l'incertitude des données et les combinaisons rigides justifient la prudence (S1). |
| `penalty_slope_deg` | 10° | 8° | Zone de vigilance accrue ; vitesse réduite et risque de chute augmenté. |
| `scarp_buffer_m` | 10 m | 20 m | Incertitude de localisation GPS + résolution données. Le tampon inclut `coreg_m` de la couche `scarps`. |
| `avoid_loose_soil_class` | 3 (dune) | 2 (meuble) | Classe 3 = dune active, risque d'enlisement. Classe 2 = sol meuble, traversée difficile. |
| `max_roughness_m` | 0,5 m | 0,3 m | Rugosité > 0,5 m = risque de trébucher avec une combinaison rigide. |

### Modèle de marche (Tobler adapté)

La vitesse de traversée utilise la formule de Tobler :

```
v(θ) = v_base × exp(−3,5 × |sin(θ) + 0,05|) / exp(−3,5 × 0,05) × facteur_sol
```

- `θ` : angle de pente en radians
- `v_base = 1,0 m/s` (SuitModel.base_speed_mps)
- `facteur_sol` : [1,0 ; 0,9 ; 0,7 ; 0,5] par classe 0–3

**Adaptations à Mars (0,38 g) :** La formule de Tobler a été établie sur Terre.
Sur Mars, la gravité réduite facilite la marche en descente et ralentit la montée
différemment. En l'absence de données expérimentales définitives pour une combinaison
rigide à 0,38 g, on conserve la forme fonctionnelle de Tobler (validée en analogues)
avec `v_base` calibré par P3. Référence : Hendricks et al. (2021), simulations de
marche en EVA lunaire ; données Apollo.

**Implémentation :** LUT (lookup table) pré-calculée sur 1800 angles (0–90°, pas 0,05°).
Précision : erreur relative < 0,1 % par rapport au calcul direct, bien en dessous de
l'incertitude de mesure de la pente (±0,5°). Gains de performance : ~7× vs sin+exp direct.

### Risque R (normalisé 0–1)

R est la somme des pénalités actives, bornée à [0, 1] :

| Pénalité | Formule | Max |
|----------|---------|-----|
| Pente intermédiaire | `(θ − penalty_slope_deg) / (max_slope_deg − penalty_slope_deg)` | 1,0 |
| Sol meuble (classe avoid−1) | 0,5 | 0,5 |
| Hors radio | `radio_penalty / (radio_penalty + 1)` | ≈0,8 |
| Ombre | `(1 − illum) × 0,3` | 0,3 |
| Rugosité | `clip(roughness / max_roughness, 0, 1) × 0,4` | 0,4 |
| Poussière | `clip((tau − max_tau) / max_tau, 0, 1) × 0,3` | 0,3 |
| Dose | `clip(dose / (max_dose/8h) − 1, 0, 1) × 0,5` | 0,5 |

Le risque total est borné à 1 par `np.clip`.

### Intérêt scientifique S (normalisé 0–1)

Basé sur la couche `crism_minerals` :
- Classe 0 (non détecté) → S = 0,0
- Classe 1 (argiles/carbonates) → S = 0,5
- Classe 2 (olivine) → S = 1,0

Justification : les argiles et carbonates sont des marqueurs d'environnements aqueux
passés (priorité scientifique haute). L'olivine indique des roches mafiques non altérées,
intéressantes pour la chronologie géologique. Source : Mustard et al. (2008), "Hydrated
silicate minerals on Mars observed by the Mars Reconnaissance Orbiter CRISM".

**Si CRISM est absent :** S = 0,0 (absence d'information ≠ absence d'intérêt ; P1 ne
prend pas de risque en attribuant un bonus non justifié).

### Dégradation gracieuse

Principe : **une donnée inconnue n'est jamais traitée comme sûre**.

| Couche absente | Comportement |
|---------------|-------------|
| `slope` | Toute la grille → 90° → tout interdit |
| `obstacles` | Toute la grille → 1 → tout interdit |
| `loose_soil` | Toute la grille → classe 3 → tout interdit |
| `scarps` | Pas de dilation, avertissement |
| `thermal_inertia` | Avertissement sur fiabilité de loose_soil |
| `radio_coverage` | Pénalité radio ignorée (cas optimiste acceptable, couche secondaire) |
| `illumination` | Pénalité ombre ignorée (couche secondaire) |
| `crism_minerals` | S = 0 (pas de bonus, neutre) |

La `margin_pct` (CostGrid.margin_pct) est non nulle dès qu'une couche critique est
dégradée ou absente. Elle est informative : la marge réelle est appliquée en amont
via les valeurs de pire cas dans les tableaux.

### Tampon de falaise

Le tampon total en cases est :

```
radius_cells = ceil((scarp_buffer_m + coreg_m + resolution_m) / resolution_m)
```

où `coreg_m` est l'incertitude de recalage de la couche `scarps` (champ
`uncertainty.coreg_m` du manifeste). Cela garantit que l'incertitude géographique
est prise en compte.

La dilation utilise deux passes de `maximum_filter1d` (approximation carré),
ce qui est légèrement plus conservative qu'un disque — ce conservatisme est volontaire
pour un tampon de sécurité.

### Performance

Critère : 5×5 km à 2 m (2500×2500 cases) < 1 s sur l'environnement de référence Linux/CI (hors I/O disque).

Résultats mesurés (environnement de référence, couches cachées) :

| Phase | 1000×1000 | Extrapolé 2500×2500 |
|-------|-----------|---------------------|
| load_layers (COG cachés) | ~5 ms | ~5 ms (invariant) |
| build_masks | ~40 ms | ~250 ms |
| compute_cost_grid | ~200 ms | ~600 ms |
| **Total calcul** | **~245 ms** | **~855 ms** |

La simulation directe sur 2500×2500 (`test_numpy_computation_2500x2500`) mesure
~700 ms sur Linux/CI, en dessous du seuil de 1 s. Sur Windows, la variabilité
du scheduler et des bibliothèques BLAS peut donner jusqu'à ~1,2 s ; le test
tolère 2 s sur cette plateforme pour ne pas être flaky.

L'I/O initiale (lecture des 15 COG depuis le disque) prend ~600 ms à froid ; les
appels suivants utilisent le cache de `site._cache` et sont négligeables.

---

## Exécution

```bash
# Depuis la racine du monorepo
uv run pytest planner/tests/p1/ -v

# Avec profil temporel affiché
uv run pytest planner/tests/p1/test_performance.py -v -s
```
