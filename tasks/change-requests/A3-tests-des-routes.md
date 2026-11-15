# Demande de changement A3 : tests des routes du socle

**Auteur :** agent A3
**Date :** 2026-11-14
**Statut :** proposé, appliqué par la PR « [T00] Tests des routes : ne comparer aux exemples que les bouchons » (branche `t00/tests-bouchons`)

- **Champ ou route** : `api/tests/test_routes.py` (T00).
- **Raison** : ce fichier compare chaque route à son exemple de `contracts/examples/`. Une fois les routes d'A3 implémentées (alertes, conditions, scénarios, temps, WebSocket), leurs réponses ne sont plus les exemples et le test échoue, alors qu'A3 ne peut pas modifier ce fichier.
- **Effet sur les autres tâches** : la comparaison ne porte plus que sur les routes dont le routeur est encore un bouchon (docstring « Bouchon T00 »). Chaque tâche qui implémente un routeur retire cette mention de sa docstring et met ses tests dans `api/tests/<id>/`. A1, A2, A4, G1 et X1 bénéficient du même mécanisme.
- **Contournement** : aucun ; la PR d'A3 dépend de celle de T00.
