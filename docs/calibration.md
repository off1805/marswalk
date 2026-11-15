# Calibration sur Jezero (I1)

Ce document consigne la bascule de Marswalk du site fictif vers le cratère Jezero : ce qui a été ajusté sur le vrai relief, pourquoi, et les mesures de performance sur la vraie grille (ENF-02). Les mesures ont été prises le 15 novembre 2026 sur un conteneur de 4 cœurs et 15 Go, à partir des rasters alignés de D1 (`data/work/jezero/aligned/`).

## Construire le paquet

```bash
make site SITE=jezero            # ingest (D1), derive (D2), package (D3)
make site-package SITE=jezero    # sans refaire l'ingestion, si data/work/jezero/aligned existe déjà
```

`site-package` copie la provenance des couches (`config/sites/jezero/layers/*.json`) dans `data/work/jezero/layers/`, calcule les couches dérivées puis écrit et valide `data/packages/jezero/`. Le paquet obtenu fait 588 Mo (limite ENF-10 : 2 Go) et passe le validateur. `docker compose` monte `data/packages/` dans l'API, et l'API choisit Jezero par défaut dès que son paquet est présent (sinon le site fictif).

## Ce qui a été ajusté

| Réglage | Avant | Après | Raison |
| --- | --- | --- | --- |
| Rugosité (D2, code) | écart type brut de l'altitude, en float32 | écart quadratique au relief moyen local, en float64 | En float32, `E[x²] − E[x]²` sur des altitudes de −2 500 m ne garde aucune précision : la rugosité valait 0 ou 1 m et **99,4 % de l'emprise était classée obstacle**. L'écart type brut comptait aussi la pente régionale comme rugosité. |
| `obstacle_roughness_threshold_m` | 0,4 m | 0,25 m | Avec la rugosité corrigée, 0,4 m ne marque que 0,09 % de l'emprise. À 0,25 m : 0,4 % (0,7 % avec le tampon de 2 m), surtout le front du delta et les buttes. |
| Couverture radio (D2, code) | 3 600 rayons, horizon calculé sur la tête de l'observateur | un rayon par pixel au bord de l'emprise, horizon sur le sol | À 3,5 km, 3 600 rayons laissent 6 m entre deux rayons : la couverture était mitée (0,85 %). L'horizon doit se calculer sur le relief, pas sur le relief plus 1,8 m. |
| `antenna_height_m` | 3 m | 10 m | Mât de l'habitat. À 3 m, le relief du fond du cratère ne laisse que 19 % de l'emprise en vue ; à 10 m, 42 % ; à 20 m, 65 %. |
| `rover` | `{x: 100, y: 100}` (fictif) | 77,40846° E, 18,45864° N | Perseverance est aujourd'hui à plus de 12 km à l'ouest, hors de l'emprise. On prend son dernier arrêt dans l'emprise (sol 707, `M20_waypoints.json` du JPL), au pied du delta. |
| `habitat` | centre | centre (inchangé) | Le centre est à 22 m du site d'atterrissage (Octavia E. Butler), sur le fond plat du cratère. |
| Seuils de `safety.yaml` | standard et prudent | inchangés | Avec les couches corrigées, le préréglage standard interdit 2,9 % de l'emprise et les quatre cibles de S1 sont joignables, avec un retour garanti à 77 % de réserve. Rien n'impose de les changer. |

Les couches portent leur provenance (instrument, produit, URL, incertitude de recalage tirée de `coreg_report.md`). `crism_minerals` est marquée `degraded` : les deux cubes MTRDR ne couvrent qu'environ la moitié de l'emprise, et P1 applique alors la marge de 15 %.

## Zones « hors radio » (après I2)

Sur Jezero, 57 % de l'emprise est hors de vue du mât de l'habitat, et `GET /hazards` dessinait toute cette surface en orange. Deux changements : le rover relaie la radio (`rover_antenna_height_m`, 2 m par défaut), ce qui porte la couverture à 51 % ; et la cause `no_radio` n'est dessinée que si le préréglage exige la radio (`require_radio`, vrai en « prudent »). La pénalité reste dans la grille de coût dans tous les cas.

## Correctifs nécessaires hors de I1

Faits dans une PR séparée (`fix/I1-jezero`), parce qu'ils touchent D2, P1, P2, P3, A2 et la coquille du front :

- **P1, grille de planification à 2 m.** Le paquet est à 1 m (5 000 × 5 000 cases) et P1 planifiait à la résolution du paquet : la grille de coût prenait 7 s et le champ de retour saturait 15 Go de mémoire. P1 agrège désormais les couches par blocs de 2 × 2 en gardant le pire (pente, obstacles, falaises, sol meuble au maximum ; radio et éclairement au minimum), et garde en cache les grilles déjà construites.
- **P3, champ de retour.** Au-delà d'un million de cases, il est calculé sur une maille agrégée (6 m à Jezero), puis rééchantillonné : 0,7 s au lieu de 7 s.
- **P2, tronçons décalés.** Les débuts de tronçon pointaient un point trop loin : le premier tronçon englobait le début du second et le dernier valait 0 m. Corrigé, et le champ de retour est calculé une fois par plan au lieu d'une fois par variante.
- **A2.** L'API ne connaissait que les cibles et les réglages d'exemple du site fictif. Les sites réels reçoivent maintenant leurs cibles de `targets-seed.geojson` (J1 à J4) et le préréglage par défaut de `safety.yaml`. `MARSWALK_WARMUP=true` prépare les grilles au démarrage.
- **Front.** Une liste déroulante dans la barre du haut choisit le site ; au démarrage, Jezero est pris s'il est servi par l'API (ou `?site=`, ou `VITE_DEFAULT_SITE`).

## Mesures (ENF-02)

`uv run python config/sites/jezero/calibration/bench.py` refait ces mesures sur le paquet installé.

| Mesure | Objectif | Jezero |
| --- | --- | --- |
| Grille de coût, 2 500 × 2 500 à 2 m | < 1 s | 0,5 s (4,8 s à la première lecture des couches) |
| Zones dangereuses en GeoJSON | — | 1,1 à 1,5 s |
| Champ de retour | < 2 s | 0,7 à 1,6 s |
| Plan à 3 variantes, 4 cibles, API préchauffée | < 5 s | 0,8 à 4,0 s |
| Premier plan sans préchauffage | < 5 s | 7 à 11 s : **non tenu**, d'où `MARSWALK_WARMUP` |
| Recalcul après déplacement d'une cible | < 2 s (P2), < 5 s (ENF-02) | 2,9 s : tient ENF-02, pas la cible de 2 s de P2 |
| Interrogation d'un point, API préchauffée | — | 0,01 s |

L'essentiel du temps restant est la recherche de chemin de P2 (Dijkstra de SciPy sur une fenêtre autour de chaque tronçon, environ 0,2 s par tronçon et 15 tronçons pour 4 cibles et 3 variantes). Pour passer sous 2 s au recalcul, la piste est une recherche A* bornée ou `MCP_Geometric` de scikit-image, à confier à P2.

## Itinéraires obtenus

Plan sur les quatre cibles de S1, préréglage standard, départ et retour à l'habitat :

| Variante | Distance | Durée (marche et travail) | Pente maximale | Retour |
| --- | --- | --- | --- | --- |
| La plus sûre | 6,29 km | 4,0 h | 19,1° | garanti, 77 % de réserve |
| La plus rapide | 6,27 km | 4,0 h | 19,1° | garanti, 78 % |
| La plus riche en science | 6,28 km | 4,0 h | 19,1° | garanti, 78 % |

Ordre retenu : habitat, J1 (front du delta), J4 (Kodiak), J2 (Séítah), J3 (contact Séítah et Máaz), habitat. Les trois variantes ne diffèrent que de quelques dizaines de mètres : sur le fond du cratère, peu de zones pénalisées séparent les cibles. La pente maximale de 19,1° frôle le seuil d'interdiction (20°) sur l'approche du delta ; c'est cohérent avec le relief, et le préréglage prudent (15°) l'évite.

## Reste à faire

- **HiRISE à 25 cm.** D1 a rééchantillonné l'orthomosaïque à 1 m ; les tuiles s'arrêtent donc au zoom 17. Pour atteindre le zoom 19, il faut une version pleine résolution dans `data/work/jezero/display/hirise_vis.tif` (D1).
- **Trajet du rover et images au sol.** `rover_traverse` et `ground_images` sont `missing` tant que G1 n'a pas tourné sur l'ordinateur qui a accès au JPL.
- **Validation visuelle.** La superposition des couches dans QGIS (`qgis/jezero.qgz`) reste à valider par la personne (D1).
