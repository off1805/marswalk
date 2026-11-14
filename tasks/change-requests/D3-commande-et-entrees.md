# Demande de changement D3 : commande `marswalk package`, cible `make site` et entrées du paquet

**Auteur :** agent D3
**Date :** 2026-11-14
**Statut :** proposé

## 1. Commande `marswalk package` et cible `make site`

- **Champ ou route** : `pipeline/pyproject.toml` (fichier partagé, ajout de dépendances seulement) et `Makefile` (T00).
- **Demande** : ajouter `[project.scripts] marswalk = "marswalk_pipeline.cli:main"` avec un point d'entrée commun aux sous-commandes `ingest` (D1), `derive` (D2) et `package` (D3), et dans le `Makefile` :

  ```make
  site: ## Paquet réel : make site SITE=jezero
  	uv run python -m marswalk_pipeline.ingest $(SITE)
  	uv run python -m marswalk_pipeline.derived $(SITE)
  	uv run python -m marswalk_pipeline.package $(SITE)
  ```
- **Raison** : la fiche D3 demande `marswalk package <site_id>` et `make site SITE=jezero`, qui sortent du périmètre de D3.
- **Effet sur les autres tâches** : D1 et D2 exposent un module exécutable (`python -m marswalk_pipeline.ingest <site_id>`, `python -m marswalk_pipeline.derived <site_id>`).
- **Contournement** : `python -m marswalk_pipeline.package <site_id>`, déjà livré.

## 2. Entrées attendues de D1, D2 et G1

- **Champ** : dossier `data/work/<site_id>/` (décrit dans `pipeline/marswalk_pipeline/package/README.md`).
- **Demande** : D1 écrit `aligned/<id>.tif` et, pour HiRISE, la version pleine résolution `display/hirise_vis.tif` ; D2 écrit `derived/<id>.tif` sur la grille de `aligned/dem.tif` ; D1, D2 et G1 écrivent `layers/<id>.json` (source, date, résolution, incertitude, statut) ; G1 écrit `vector/<id>.geojson` et `thumbs/`.
- **Raison** : la provenance (ENF-04) et la netteté au zoom 19 (section 4) demandent ces informations, que les seuls rasters ne portent pas. Sans `display/`, la grille d'analyse à 1 m limiterait HiRISE au zoom 17.
- **Effet sur les autres tâches** : D1 (fiche : « écrit `data/work/jezero/aligned/<layer_id>.tif` ») ajoute `display/` et `layers/` ; D2 et G1 ajoutent `layers/`.
- **Contournement** : une couche sans `layers/<id>.json` est publiée avec une source « INCONNU » ; une couche sans fichier est déclarée `missing`.
