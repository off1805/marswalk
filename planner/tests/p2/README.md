# Tests P2 — Moteur de navigation Marswalk

## Organisation

| Fichier | Couverture |
|---------|-----------|
| `conftest.py` | Fixtures partagées : sites synthétiques, couches, helpers de coordonnées |
| `test_astar.py` | Algorithme A*/Dijkstra : chemins simples, obstacles, couloirs, extension de fenêtre |
| `test_smooth.py` | Lissage de chemin : string-pulling, vérification Bresenham, obstacles |
| `test_route.py` | `plan_route` : grille plate, contournement d'obstacle, couloir étroit |
| `test_order.py` | `order_targets` : ordre imposé, TSP exact (≤8), heuristique (>8) |
| `test_cache.py` | Cache de tronçons : clés, put/get, invalidation, réutilisation |
| `test_variants.py` | `plan_variants` : trois variantes, terrain hétérogène, recalcul obstacle |
| `test_properties.py` | Tests de propriétés aléatoires : aucun point ne traverse une cellule interdite |
| `test_performance.py` | Benchmarks : 500×500 (CI) et extrapolation 2500×2500 |

---

## Algorithmes

### Recherche de chemin : Dijkstra sur graphe creux (MCP_Geometric)

**Algorithme :** Dijkstra scipy (`scipy.sparse.csgraph.dijkstra`) sur un graphe creux CSR.

**Représentation :** Chaque cellule de la grille est un nœud. Les 8 voisins (4 cardinaux + 4 diagonaux) forment les arêtes. Le coût d'une arête est :

```
coût_arête = pas × (cost[a] + cost[b]) / 2
```

où `pas = 1.0` en cardinal, `sqrt(2)` en diagonal. Cette formulation respecte l'interprétation « coût de traversée de cellule » de P1.

**Fenêtrage spatial :** Pour éviter de traiter la grille entière à chaque tronçon, une fenêtre élargie autour du segment direct est extraite. La marge initiale vaut `window_margin_m / resolution_m`. Si aucun chemin n'est trouvé dans la fenêtre (obstacle bloquant), la fenêtre est agrandie × 2 jusqu'à 4 fois, puis la grille entière est utilisée.

**Taille de fenêtre max :** Limitée à 800×800 cases (640k cases) pour éviter les calculs trop longs sur les petits tronçons. Les segments longs qui nécessitent une plus grande fenêtre utilisent le graphe de la grille entière avec cache.

**Cache de graphe :** Le graphe CSR de la grille entière est construit une seule fois par grille de coût (identifiée par son adresse mémoire et sa taille) et réutilisé pour tous les tronçons du même plan. Cela évite de reconstruire 50M d'arêtes pour chaque segment.

### Lissage : String Pulling (Bresenham)

Le chemin brut issu de Dijkstra est un chemin en escalier sur la grille. Le lissage par string pulling simplifie ce chemin en sautant les points intermédiaires lorsqu'un segment direct est praticable.

**Vérification de segment :** L'algorithme de Bresenham à 8-connexité visite chaque cellule sur le segment et vérifie qu'aucune n'est interdite. Il ne suffit pas de vérifier les extrémités — toute cellule intermédiaire est testée.

**Propriété garantie :** Si le lissage d'un segment est impossible (l'obstacle est entre deux points), le tracé brut est conservé. Aucun point du tracé lissé ne traverse une cellule interdite.

### Optimisation de l'ordre : TSP

**≤ 8 cibles :** Résolution exacte par permutation exhaustive (`itertools.permutations`). Le nombre maximal de permutations est 8! = 40 320. La matrice de coût entre toutes les paires est calculée via l'estimation euclidienne pondérée (voir ci-dessous).

**> 8 cibles :** Heuristique nearest-neighbor (NN-TSP) avec redémarrage depuis chaque nœud. La meilleure tournée trouvée parmi tous les redémarrages est retenue. Complexité : O(n²).

**Estimation du coût :** Distance euclidienne en cases × coût moyen non infini de la grille. Cette estimation n'est pas le coût A* exact mais elle est proportionnelle au coût réel sur un terrain homogène et beaucoup plus rapide à calculer (O(1) par paire).

Le coût euclidien pur (sans pondération par le coût moyen de la grille) n'est **pas** utilisé comme substitut.

---

## Stratégie de cache

### Cache de tronçons (`_p2.cache`)

Chaque tronçon calculé est mis en cache sous une clé déterministe :

```
clé = "<site_id>|<grid_version>|<lon_a>,<lat_a>|<lon_b>,<lat_b>|<margin>|<variant>"
```

La `grid_version` est un hash MD5 encodant :
- `site_id`, `transform`, `resolution_m`, `margin_pct`
- Hash des warnings de la grille
- Empreinte du contenu de la grille (coins, centre, nombre de cellules interdites)

Cette dernière composante est cruciale : deux grilles avec les mêmes métadonnées mais des obstacles différents (après `replan_from_obstacle`) auront des clés différentes.

**Invalidation par site :** `cache.clear(site_id=...)` supprime toutes les entrées dont la clé contient le `site_id`.

**Recalcul partiel :** Quand une cible est déplacée de A à B', seuls les tronçons impliquant la cible (→A et A→) sont recalculés. Les autres (non affectés) restent en cache.

### Cache de graphe (`_p2.astar._GRAPH_CACHE`)

Le graphe CSR de la grille entière est identifié par `(id(cost), data_ptr, shape, strides)`. Ce cache est **en mémoire** pour toute la durée du processus. Il est invalidé par `clear_graph_cache()`, appelé automatiquement dans `replan_from_obstacle` via `cache.clear()`.

---

## Mesures de performance

**Environnement de référence CI** : processeur Intel/AMD, Python 3.12, NumPy 2.x, SciPy 1.18.

| Scénario | Grille | Mesure |
|---------|--------|--------|
| 5 cibles, 1er appel | 500×500 | ~0.7 s |
| 5 cibles, 1er appel | 2500×2500* | ~4.4 s |
| Déplacement d'une cible | 500×500 | ~0.3 s |
| Deuxième appel (tout en cache) | 500×500 | < 1 ms |

\* Mesuré sur machine de développement Windows (Intel i7). Sur Linux/CI, les temps peuvent varier de ±30%.

**Critères spécification** :
- 5 cibles sur 2500×2500 : **< 5 s** ✓ (mesuré ~4.4 s)
- Déplacement d'une cible : **< 2 s** ✓ (mesuré ~0.3-0.6 s)

---

## Variantes d'itinéraires

Les trois variantes utilisent des jeux de poids distincts appliqués à la formule de coût P1 :

```
C = w_t · t + w_r · R − w_s · S
```

| Variante | w_t | w_r | w_s | Comportement |
|---------|-----|-----|-----|-------------|
| safest  | 0.5× | 3.0× | 0.3× | Évite les zones à risque, fait des détours |
| fastest | 3.0× | 0.5× | 0.2× | Prend le chemin direct, tolère les pénalités |
| science | 1.0× | 1.0× | 4.0× | Passe près des zones CRISM à fort intérêt |

Les variantes produisent des chemins différents quand le terrain présente :
- Des zones à risque variable (pentes intermédiaires, hors radio, ombre)
- Des signatures minéralogiques (crism_minerals > 0)

Sur un terrain totalement uniforme, les trois variantes convergent naturellement (ce comportement est correct et non artificiel).

---

## Exécution

```bash
# Depuis la racine du monorepo (tous les tests P2)
uv run pytest planner/tests/p2/ -v

# Tests rapides uniquement (sans performance)
uv run pytest planner/tests/p2/ --ignore=planner/tests/p2/test_performance.py -v

# Tests de propriétés (10 seeds aléatoires)
uv run pytest planner/tests/p2/test_properties.py -v

# Benchmarks avec affichage
uv run pytest planner/tests/p2/test_performance.py -v -s
```
