# Demande de changement A4 : source des plans et carnet de terrain

**Auteur :** agent A4
**Date :** 2026-11-14
**Statut :** proposé

- **Champ ou route** : plans de A2 (`api/marswalk_api/routers/plans.py`) et carnet de X1 (`api/marswalk_api/routers/export.py`).
- **Raison** : `POST /api/eva` démarre une sortie sur une variante d'un plan, et ces plans appartiennent à A2. Aujourd'hui le simulateur lit le plan de démonstration `plan-demo` et les plans qu'on lui enregistre. Les plans calculés par A2 ne lui parviennent pas encore.
- **Demande à A2** : après chaque calcul ou mise à jour d'un plan, appeler `get_simulator().plans.register(plan)` (`marswalk_api.services.a4`). Autre possibilité : I2 branche le dépôt de A2 sur `get_simulator().plan_source`, qui accepte toute fonction `plan_id -> Plan | None`.
- **Demande à X1** : le carnet d'une sortie est tenu par le simulateur. `get_simulator().logbook(eva_id)` renvoie un `Logbook` qui contient le départ, l'arrivée à chaque cible, les observations, les alertes, les obstacles, les recalculs et la fin de sortie. `get_simulator().observations(eva_id)` donne les observations.
- **Effet sur les autres tâches** : aucun contrat ne change. `eva-demo` est créée à la demande sur `plan-demo` / `route-safest`, comme les exemples.
- **Contournement** : en attendant, une sortie ne peut démarrer que sur `plan-demo` ou sur un plan enregistré.
