# Demande de changement C1 — chemin de `marstime_vectors.json`

**Auteur :** agent C1  
**Date :** 2026-11-14  
**Statut :** proposé

## Contexte

La fiche de la tâche C1 dans `taches-agents.md` (§10) précise :

> Un fichier de cas de test commun, `packages/core/tests/marstime_vectors.json`, est lu par les deux implémentations.

Ce chemin est à la racine de `packages/core/tests/`, donc en dehors du sous-dossier `packages/core/tests/c1/**` actuellement listé dans `tasks/ownership.yaml` pour la tâche C1.

## Demande

Ajouter dans `tasks/ownership.yaml`, section `C1.paths` :

```yaml
- packages/core/tests/marstime_vectors.json
```

## Raison

Le fichier doit être **partagé** entre les tests Python (qui l'importent directement) et les tests TypeScript (qui l'importent via un `readFileSync` relatif). Le placer dans `c1/` oblige les deux suites à descendre dans un sous-dossier, ce qui est moins naturel et plus fragile lors d'une réorganisation future.

## Effet sur les autres tâches

Aucun effet direct : le fichier est en lecture seule pour toutes les tâches. Il ne contient que des vecteurs de test.

## Solution de contournement actuelle

Dans l'attente de ce changement, le fichier est placé à `packages/core/tests/c1/marstime_vectors.json` (dans le périmètre C1). Les tests Python et TypeScript ont leurs chemins mis à jour en conséquence.

Si la demande est acceptée, déplacer le fichier vers `packages/core/tests/marstime_vectors.json` et mettre à jour les deux imports.
