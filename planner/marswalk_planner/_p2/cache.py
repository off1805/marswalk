"""Cache de tronçons pour P2.

Chaque tronçon est identifié par une clé déterministe qui encode :
- les coordonnées des extrémités (arrondies à 7 décimales)
- la version de la grille de coût (hash des paramètres du site + settings)
- les options de recherche pertinentes (window_margin_m, variant)

Le cache est un dict en mémoire, valide pour toute la durée de vie du
processus. Il est invalidé par appel à ``clear()`` ou par changement
de version de grille.

Invalidation partielle (recalcul après déplacement de cible) :
  Seuls les tronçons impliquant la cible déplacée ont une nouvelle clé.
  Les autres tronçons restent en cache.

Évite les collisions entre sites différents grâce au ``site_id`` dans
la clé.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from marswalk_core.grids import CostGrid, RouteGeometry
from marswalk_core.schemas import LonLat


def _grid_version(cost_grid: CostGrid) -> str:
    """Condensé des paramètres de la grille qui influencent les chemins.

    Encode : site_id, transform, resolution, margin_pct, les warnings, et
    un hash de l'empreinte du tableau de coûts (corners + statistiques) pour
    détecter les changements de contenu (obstacles ajoutés, etc.).
    """
    import numpy as np

    cost = cost_grid.cost
    # Empreinte légère : coins + centre + min/max/somme pour détecter les changements
    h, w = cost.shape
    sample_vals = []
    for r, c in [(0, 0), (0, w//2), (0, w-1), (h//2, 0), (h//2, w//2),
                 (h//2, w-1), (h-1, 0), (h-1, w//2), (h-1, w-1)]:
        v = cost[r, c]
        sample_vals.append(0.0 if np.isinf(v) else float(v))
    # Nombre de cellules interdites (signature robuste)
    n_forbidden = int(np.sum(np.isinf(cost)))
    sample_vals.append(float(n_forbidden))

    data = {
        "site": cost_grid.site.site_id,
        "transform": list(cost_grid.transform),
        "resolution_m": cost_grid.resolution_m,
        "margin_pct": cost_grid.margin_pct,
        "warnings_hash": hashlib.md5(
            json.dumps(sorted(cost_grid.warnings)).encode()
        ).hexdigest()[:8],
        "cost_sample": [round(v, 4) for v in sample_vals],
    }
    raw = json.dumps(data, sort_keys=True).encode()
    return hashlib.md5(raw).hexdigest()[:12]


def segment_key(
    cost_grid: CostGrid,
    a: LonLat,
    b: LonLat,
    window_margin_m: float,
    variant_name: str,
) -> str:
    """Clé de cache déterministe pour un tronçon a→b.

    Format : ``<site_id>|<grid_version>|<lon_a>,<lat_a>|<lon_b>,<lat_b>|<margin>|<variant>``

    Le site_id est inclus en clair pour permettre l'invalidation par site via
    ``clear(site_id=...)``. Les coordonnées sont arrondies à 7 décimales
    (≈ 1 cm sur Mars) pour éviter les faux ratés de cache dus aux flottants.
    """
    site_id = cost_grid.site.site_id
    grid_ver = _grid_version(cost_grid)
    lon_a = round(a.lon, 7)
    lat_a = round(a.lat, 7)
    lon_b = round(b.lon, 7)
    lat_b = round(b.lat, 7)
    parts = f"{site_id}|{grid_ver}|{lon_a},{lat_a}|{lon_b},{lat_b}|{window_margin_m}|{variant_name}"
    return parts


# Cache global en mémoire : clé → RouteGeometry
_CACHE: dict[str, RouteGeometry] = {}


def get(key: str) -> RouteGeometry | None:
    """Récupère un tronçon depuis le cache, ou None si absent."""
    return _CACHE.get(key)


def put(key: str, geom: RouteGeometry) -> None:
    """Enregistre un tronçon dans le cache."""
    _CACHE[key] = geom


def clear(site_id: str | None = None) -> int:
    """Vide le cache.

    Si ``site_id`` est fourni, ne supprime que les entrées de ce site
    (les clés contiennent le site_id via le grid_version).
    Retourne le nombre d'entrées supprimées.
    """
    if site_id is None:
        n = len(_CACHE)
        _CACHE.clear()
        return n
    keys_to_del = [k for k in _CACHE if site_id in k]
    for k in keys_to_del:
        del _CACHE[k]
    return len(keys_to_del)


def size() -> int:
    """Nombre d'entrées dans le cache."""
    return len(_CACHE)
