# Demande de changement : ajout de D2_REPORT.md au périmètre D2

**Tâche demandeuse :** D2 — Couches dérivées  
**Fichier cible :** `tasks/ownership.yaml`  
**Propriétaire :** T00

## Contexte

La branche `task/D2-derived-layers` produit un rapport `D2_REPORT.md` à la racine du dépôt.
Ce fichier n'est pas encore listé dans les chemins de D2 dans `tasks/ownership.yaml`, ce qui
bloque le contrôle d'ownership en CI.

## Modification demandée

Dans la section `tasks.D2.paths` de `tasks/ownership.yaml`, ajouter :

```yaml
- D2_REPORT.md
```

## Justification

`D2_REPORT.md` est un livrable direct de la tâche D2 (documentation des couches dérivées).
Il n'empiète sur aucun autre périmètre et ne modifie aucune interface partagée.
