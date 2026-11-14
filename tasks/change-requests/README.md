# Demandes de changement de contrat

Les contrats sont gelés à l'étiquette `contrats-v1` : `contracts/`, `packages/core/marswalk_core/schemas.py`, `web/src/shared/store.ts`, `web/src/app/registry.ts`, `web/src/app/feature.ts` et la migration `0001_initial`.

Une tâche qui a besoin d'un changement ne modifie pas ces fichiers. Elle écrit `tasks/change-requests/<ID>-<sujet>.md` avec :

- **Champ ou route** concerné ;
- **Raison** du besoin ;
- **Effet sur les autres tâches** (qui doit adapter quoi) ;
- **Contournement** appliqué en attendant dans son périmètre.

Elle le signale dans sa PR. La personne ou un agent intégrateur applique les demandes groupées dans une PR `contracts-v2` (branche hors du motif `task/`), relance `make contracts` et `make examples`, puis les branches en cours rebasent.
