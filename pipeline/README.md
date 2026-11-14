# marswalk-pipeline

Pipeline de données Marswalk : ingestion (D1), couches dérivées (D2), paquet de site (D3), images au sol (G1).

## D2 — Couches dérivées

Produit toutes les couches calculées à partir du MNT, de l'imagerie et de THEMIS.

### Couches produites

| Couche | Description | Paramètres `site.yaml` |
|--------|-------------|------------------------|
| `slope` | Pente en degrés (différences finies centrées) | — |
| `roughness` | Écart type local du MNT | `roughness_window_m` (défaut 10 m) |
| `hillshade` | Ombrage (azimut 315°, hauteur 45°) | — |
| `obstacles` | Masque de blocs + tampon | `obstacle_roughness_threshold_m`, `obstacle_buffer_m` |
| `scarps` | Ruptures de pente + tampon | `scarp_threshold_deg`, `scarp_buffer_m` |
| `loose_soil` | Classe de sol (inertie thermique + pente) | — |
| `radio_coverage` | Visibilité radio depuis l'habitat | `antenna_height_m` |
| `illumination` | Fraction éclairée (algorithme d'horizon) | `sun_azimuth_deg`, `sun_altitude_deg` |

### Utilisation

```bash
# Via la commande CLI
marswalk-derive fictif

# Via Python
from marswalk_pipeline.derived import derive
from pathlib import Path
derive(Path("fixtures/sites/fictif"))
```

### Algorithmes

- **Pente** : différences finies centrées (Zevenbergen & Thorne 1987), calcul en mètres (R1).
- **Rugosité** : écart type local par filtre uniforme scipy.ndimage sur fenêtre réglable.
- **Ombrage** : formule ESRI/GDAL, azimut 315°, hauteur 45°.
- **Obstacles** : rugosité > seuil (0,4 m par défaut), dilatation morphologique (tampon réglable).
- **Scarps** : pente > 30° + dilatation morphologique (tampon 10 m par défaut).
- **Sol meuble** : inertie thermique THEMIS + pente → 4 classes (roche/mixte/meuble/dune).
- **Couverture radio** : lancer de rayons vectorisé (32 échantillons) depuis l'habitat.
- **Illumination** : algorithme d'horizon projeté O(H×W) — passe unique dans la direction du Soleil.

### Tests

```bash
uv run pytest pipeline/tests/d2/ -v
```

Critères d'acceptation couverts :
- ✅ Falaise dans `scarps` (site fictif)
- ✅ Dunes dans `loose_soil` (classe 3)
- ✅ Point caché par cratère → hors couverture radio
- ✅ Plan incliné 15° retrouvé à 0,1° près
- ✅ Calcul complet < 60 s sur site fictif (1000×1000, 2 m)
