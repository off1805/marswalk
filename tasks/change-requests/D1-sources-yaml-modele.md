# Demande de changement D1 : modèle sources.yaml

**Tâche :** D1 — Ingestion et recalage des données réelles de Jezero  
**Champ :** `config/sites/jezero/sources.yaml`  
**Propriétaire actuel :** D0

## Raison

La tâche D1 a besoin d'un fichier `config/sites/jezero/sources.yaml` pour
documenter les produits PDS à télécharger et les chemins de fichiers attendus
dans `data/raw/jezero/`. Ce fichier décrit les sources de chaque couche
(identifiant PDS, URL Mars Trek, date, nom de fichier local).

D0 possède ce fichier selon `ownership.yaml`. Un modèle documentant les
produits PDS retenus pour Jezero a été préparé par D1 dans la branche
`task/D1-ingestion-recalage` mais **ne peut pas être versionné dans D1**.

## Contournement dans D1

- La tâche D1 (`ingest.py`) charge `sources.yaml` s'il existe, et renvoie
  des résultats `status="missing"` si les fichiers sources sont absents.
- Les tests D1 utilisent `ingest_from_package("fictif", ...)` qui ne dépend
  pas de `sources.yaml`.
- Le modèle proposé se trouve dans la PR D1 en description (ou en brouillon
  dans `tasks/change-requests/`).

## Effet sur les autres tâches

- **D0** doit créer `config/sites/jezero/sources.yaml` avec les produits PDS
  retenus avant que `marswalk ingest jezero` puisse s'exécuter sur les vraies
  données.
- **I1** dépend du `sources.yaml` pour la bascule sur Jezero.

## Modèle proposé

Voir le contenu dans `tasks/change-requests/D1-sources-yaml-modele.yaml`
(copié depuis la branche D1 par D0 lors de la fusion).
