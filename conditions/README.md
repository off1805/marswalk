# Conditions martiennes et scénarios (K1)

Paquet Python `marswalk_conditions` : conditions du moment et prévisions à Jezero, réelles
(MEDA, RAD), rejouées (scénario `solar-event`) ou en direct (DONKI). Interface gelée :
`get_provider(mode, scenario_id)` et `list_scenarios()` (section 7 de `taches-agents.md`).

## Importer les données réelles

Les fichiers bruts sont téléchargés par D0 dans `data/raw/jezero/meda/` et
`data/raw/jezero/rad_may2024/`. L'import en tire un jeu compact (quelques centaines de Ko au
plus), hors Git comme toutes les données réelles :

```bash
uv run python -m marswalk_pipeline.fetch jezero --only meda,rad_may2024   # si besoin (D0)
uv run python -m marswalk_conditions import      # écrit data/work/conditions/jezero.json
uv run python -m marswalk_conditions show        # résumé : sols, fond, début et pic RAD
```

`MARSWALK_CONDITIONS_FILE` change l'emplacement du jeu compact. Sans ce fichier, tout
fonctionne sur des modèles de repli, et chaque `Conditions.source` le dit.

| Donnée | Produit (D0) | Ce qui est retenu |
| --- | --- | --- |
| Température de l'air | MEDA `CAL_ATS` | moyenne des capteurs 1 à 3 du mât, K vers °C |
| Pression | MEDA `CAL_PS` | `BAROCAP1_PRESSURE` (transducteur actif), Pa |
| Vent | MEDA `CAL_WS` | moyenne des deux mâts, vitesse horizontale, m/s |
| Débit de dose | MSL RAD RDR (Curiosity, Gale) | `DOSIMETRY_TOTAL_DOSE_E` (plastique, proche du tissu), µGy/h, daté au milieu de la pose |

Les mesures MEDA sont moyennées par demi-heure d'heure solaire locale (LMST) et par sol. Pour
chaque fichier, la version de produit la plus récente l'emporte (`P02` plutôt que `P01`). Les
poses RAD interrompues (dose effondrée par rapport aux deux voisines) sont écartées.

## Modes

1. **`historical`** : rejoue le sol MEDA importé qui correspond au sol de mission (les sols
   importés tournent en boucle), à l'heure locale de Jezero. Une grandeur absente ce sol-là
   (le vent n'existe que pour les sols 36 à 39) est prise dans la climatologie. Le débit de
   dose est le fond RAD mesuré avant l'événement, converti en dose équivalente.
   `forecast` donne la climatologie MEDA : moyenne de chaque demi-heure sur tous les sols.
2. **`scenario`** (`solar-event`) : rejoue l'événement à particules solaires du 20 mai 2024
   vu par RAD. Le début de l'événement tombe à t = 1 200 s, le pic quelques dizaines de
   secondes plus tard (instant exact dans l'événement `peak` de `list_scenarios()`). Une
   seconde de scénario vaut 54 s réelles : le rejeu couvre 18 h avant le début et 36 h après.
   Même entrée, même courbe : le rejeu est reproductible.
3. **`live`** : météo spatiale DONKI (clé `NASA_API_KEY`, `DEMO_KEY` par défaut), écrite à
   chaque réponse dans `data/cache/donki.json` (`MARSWALK_DONKI_CACHE`). Sans réseau, la
   dernière valeur en cache est renvoyée avec sa date `cached_at`, même après un redémarrage.

L'horloge du scénario : `get_scenario_manager().start(...)` la démarre explicitement. Sinon,
le fournisseur s'ancre sur le premier instant reçu, ce que fait A3 en faisant avancer
lui-même l'instant simulé ; un instant qui recule ou dépasse la fin repart de zéro.

## Hypothèses (à dire dans le pitch)

- **Transposition** : Perseverance n'a pas de RAD ; la dose vient de Curiosity à Gale.
- **Dose équivalente** : fond × 3,05 (facteur de qualité moyen mesuré au sol par RAD,
  Hassler et al. 2014) ; excès solaire × 1 (protons).
- **Modélisés** : l'indice UV et l'opacité de la poussière (absents des produits calibrés de
  D0), et en mode `live` le débit de dose déduit du niveau DONKI (DONKI décrit l'espace
  proche de la Terre, pas le sol martien).

## Tests

```bash
uv run pytest conditions
```

Les tests fabriquent des fichiers au format exact du PDS avec des valeurs inventées ; aucune
donnée réelle n'est versionnée.
