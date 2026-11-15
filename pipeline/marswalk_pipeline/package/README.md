# D3 : paquet de site

`python -m marswalk_pipeline.package <site_id>` lit `data/work/<site_id>/`, écrit le paquet de la section 5 de `taches-agents.md` dans un dossier temporaire, le valide avec `tools/validate_site_package.py`, puis le met en place dans `data/packages/<site_id>/`. Un paquet invalide ou trop gros ne remplace jamais le précédent.

```bash
uv run python -m marswalk_pipeline.package jezero                 # data/work/jezero -> data/packages/jezero
uv run python -m marswalk_pipeline.package fictif \
    --from-package fixtures/sites/fictif --out /tmp/fictif         # régénère le site fictif depuis ses sources
```

Options : `--work`, `--out`, `--max-mb` (2 Go par défaut, ENF-10), `--generated-at` (date du manifeste ; sinon `SOURCE_DATE_EPOCH`, sinon maintenant). Avec la même date et les mêmes entrées, deux exécutions donnent des fichiers identiques octet pour octet.

## Entrées

| Chemin dans `data/work/<site_id>/` | Écrit par | Contenu |
| --- | --- | --- |
| `aligned/<id>.tif` | D1 | Rasters recalés sur la grille d'analyse. `aligned/dem.tif` fixe la grille du paquet |
| `derived/<id>.tif` | D2 | Couches dérivées, sur la même grille |
| `display/<id>.tif` | D1, facultatif | Version pleine résolution pour les tuiles, même système (R1), grille libre. HiRISE à 0,25 m va ici ; son COG est alors rééchantillonné sur la grille (moyenne, ou mode pour les catégories) |
| `layers/<id>.json` | D1, D2, G1 | Métadonnées de la couche : `source`, `acquired`, `resolution_m`, `uncertainty`, `status` et `status_note` (`degraded`), et au besoin `title`, `unit`, `value_range`, `legend`, `display` |
| `vector/<id>.geojson` | G1 | `rover_traverse`, `ground_images` |
| `thumbs/` | G1 | Vignettes des images au sol, copiées telles quelles |

La liste des couches et `analysis_crs`, `name`, `habitat`, `rover` (`{x, y}` en mètres depuis le centre, ou `{lon, lat}`), `mission_epoch_utc`, `default_preset` et `tiles.minzoom` viennent de `config/sites/<site_id>/site.yaml`. Une couche listée sans fichier d'entrée est déclarée `missing` dans le manifeste. Le titre, la légende et les règles d'affichage par défaut sont dans `catalog.py`.

Un fichier `layers/<id>.json` minimal :

```json
{
  "resolution_m": 0.25,
  "acquired": "2019-06-12",
  "source": {"instrument": "HiRISE", "mission": "MRO", "product_id": "JEZ_hirise_soc_007", "url": "https://…"},
  "uncertainty": {"coreg_m": 0.5}
}
```

`display` accepte `resample` (`lanczos`, `average`, `nearest`), `stretch` (centiles, par ex. `[0.5, 99.5]`), `transparent` (classes à ne pas peindre) et `quality` (WebP).

## Sorties et règles de rendu

- **COG** : Float32, nodata -9999, DEFLATE avec prédicteur, blocs de 256, aperçus (moyenne, ou plus proche voisin pour les catégories), sur la grille d'analyse.
- **Zoom maximal** de chaque couche : le plus petit zoom dont le pixel ne dépasse pas la résolution de son raster source (section 4). À Jezero : HiRISE 0,25 m → 19, couches à 1 m → 17, CTX 6 m → 14 ; zoom minimal 12.
- **Zoom maximal** : échantillonnage bilinéaire des valeurs continues, plus proche voisin des catégories, au centre de chaque pixel de tuile (règles R1 et R3).
- **Zooms inférieurs** : réduction de moitié de la mosaïque des quatre tuiles filles, sur les valeurs et en ignorant le nodata : Lanczos pour l'imagerie et l'ombrage, moyenne pour les autres valeurs continues, plus proche voisin pour les catégories.
- **Encodage** : WebP de qualité 92 pour l'imagerie et 90 pour les autres couches continues, WebP sans perte pour les catégories ; contraste de l'imagerie étiré sur les centiles 0,5 à 99,5 de l'emprise.
- **Terrain-RGB** : PNG, `h = -10000 + (R × 65536 + G × 256 + B) × 0,1`, jusqu'au zoom du MNT.

## Tests

`uv run pytest pipeline/tests/d3` : site fictif régénéré valide et conforme au paquet de T00 (mêmes couches, grille, COG identiques, mêmes tuiles, tuiles catégorielles identiques au zoom maximal), alignement des pixels de tuile sur les valeurs des COG, terrain-RGB, imagerie pleine résolution jusqu'au zoom 19, refus au-delà de la taille limite sans toucher au paquet précédent, reproductibilité, couches manquantes.
