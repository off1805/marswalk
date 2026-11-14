# Images au sol de Perseverance (G1)

Cette commande construit l'index des images Mastcam-Z et Navcam prises dans l'emprise du site, le trajet du rover et les vignettes. D3 les met ensuite dans le paquet de site.

```bash
# Sur l'ordinateur de la personne : les serveurs du JPL ne sont pas joignables depuis le cloud.
python -m marswalk_pipeline.ground_images jezero --cache data/raw/jezero/ground_images
# Rejouer sans réseau ce qui a été gardé :
python -m marswalk_pipeline.ground_images jezero --from-cache data/raw/jezero/ground_images
```

## Sources

- **Arrêts et trajet du rover** : la couche « waypoints » de la carte MMGIS de Mars 2020 (`--waypoints-url`, par défaut `https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json`). C'est un GeoJSON de points `[lon, lat]` qui portent `sol`, `site` et `drive`.
- **Images** : le flux public `raw_images` de mars.nasa.gov (`--raw-url`), interrogé sol par sol. Seuls les sols où le rover est passé dans l'emprise sont interrogés.

Ces adresses viennent des pages publiques du JPL. Elles n'ont pas pu être vérifiées depuis l'environnement de développement, où les serveurs de la NASA sont bloqués. À la première exécution, vérifiez dans `ground_images_report.md` que les arrêts et les images sont bien trouvés. Si le JPL a déplacé une couche, donnez la nouvelle adresse en option.

## Position d'une image

Les images brutes ne portent pas de coordonnées. Chacune est placée à la position du rover au moment de la prise de vue :

1. d'abord sur l'arrêt de même `site` et `drive` ;
2. sinon sur le dernier arrêt connu à ce sol ou avant.

`position_source` indique laquelle des deux méthodes a été utilisée, et `azimuth_deg` donne l'azimut du mât quand il est connu.

## Sorties (`data/work/<site>/`)

| Fichier | Contenu |
| --- | --- |
| `vector/ground_images.geojson` | Une entité par image, avec `image_id`, `sol`, `instrument`, `camera`, `thumb`, `thumb_url`, `url`, `utc`, `azimuth_deg`, `site`, `drive`, `position_source` et `credit`. |
| `vector/rover_traverse.geojson` | Le trajet dans l'emprise, une ligne par passage, avec `sol_start` et `sol_end`. |
| `thumbs/<image_id>.jpg` | Les vignettes, de 256 px au plus. |
| `layers/ground_images.json`, `layers/rover_traverse.json` | La provenance, lue par D3. |
| `ground_images_report.md` | Ce qui a été trouvé, gardé ou écarté. |

Options : `--sols 1-1200`, `--per-stop 2` (images par arrêt et par caméra), `--max-images 300` (sélection répartie dans le temps), `--margin-m 250`, `--no-thumbs`.

L'acceptation de G1 demande au moins vingt images positionnées sur Jezero. La commande prévient si elle en trouve moins.
