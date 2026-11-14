# Tests du simulateur de sortie (A4)

- `test_simulator.py` : simulateur piloté pas à pas (`A4Service.step`). Il couvre l'avance le long du profil, l'arrêt pendant le travail aux cibles, les consommables, la dose et la réserve, le recalcul local après un obstacle (moins de 2 s, l'obstacle est contourné), l'écart au tracé et le retour forcé sur alerte `danger`.
- `test_demo.py` : étapes 10 à 14 du scénario de démo, jouées par les routes REST et le WebSocket en accéléré, en moins de 3 minutes.

L'horloge de A3 est fixée au matin du sol 14 (`conftest.MORNING_UTC`). Sinon l'alerte « fin de journée » forcerait le retour dès le départ. Le fournisseur de conditions imite K1 : un pic de dose arrive à 1 200 s du scénario `solar-event`.

Pour la démo en direct, `POST /api/eva/{id}/simulate {"speed": 50, "scenario_id": "solar-event"}` déroule la sortie de `plan-demo` en environ deux minutes.
