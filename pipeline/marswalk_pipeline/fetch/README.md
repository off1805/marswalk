# D0 : téléchargement des données de Jezero

Récupère dans `data/raw/jezero/` (hors Git) les produits bruts listés dans
`config/sites/jezero/sources.yaml`, avec leur provenance.

```bash
uv run python -m marswalk_pipeline.fetch jezero --dry-run          # liste et taille totale
uv run python -m marswalk_pipeline.fetch jezero                    # tout
uv run python -m marswalk_pipeline.fetch jezero --only hirise_dtm,ctx_ortho
```

- `clip: true` : lecture fenêtrée par `/vsicurl/` (GDAL) sur 5 × 5 km autour du site plus
  `margin_m` ; seuls les blocs utiles transitent. En cas d'échec, repli sur le fichier complet.
- Sinon téléchargement complet, repris là où il s'est arrêté (`*.part` + en-tête `Range`).
- `sources.lock.yaml` : date, taille, SHA-256 et URL de chaque fichier. Un fichier inscrit et
  de bonne taille n'est pas retéléchargé : une seconde exécution ne transfère rien.
- `fetch_report.md` : ce qui a été obtenu, ce qui manque et pourquoi.

| Produit | Source | Mode |
| --- | --- | --- |
| hirise_ortho, hirise_dtm, ctx_ortho, ctx_dtm | USGS, Mars 2020 TRN (aussi dans Mars Trek) | découpe / complet |
| mola_dem | USGS, MOLA 463 m global | découpe (marge 60 km) |
| themis_ti | USGS Astropedia, THEMIS TI quantitatif, tuile 00N060E (.cub ISIS) | découpe (marge 10 km) |
| crism_mtrdr | PDS Geosciences (API ODE), FRT000047A3 et FRT00005C5E | complet |
| m20_traverse | JPL MMGIS | complet |
| meda | PDS Atmosphères, MEDA calibré, sols 0 à 39 | répertoire filtré |
| rad_may2024 | PDS PPI, RAD RDR sols 4180 à 4205 | répertoire filtré |

Tests sans réseau : `uv run pytest pipeline/tests/d0`.
