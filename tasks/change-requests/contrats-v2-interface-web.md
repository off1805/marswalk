# contrats-v2 : une seule interface web

Demandé par la personne le 14 novembre 2026, appliqué par T00 avant le démarrage de la vague 1.

- **Champ ou route** : `web/src/shared/store.ts` (`Mode` devient `"map" | "3d"`), `web/src/app/feature.ts` (emplacements `hud-center` et `hud-corner`, type `HudWidget` et champ `hudWidgets` supprimés), `web/src/app/registry.ts` (fonctionnalité `hud` retirée), routes `/tablet` et `/hud` supprimées. `CONTRACTS_VERSION` passe à `contrats-v2`.
- **Raison** : Marswalk n'a qu'une interface web, pour un écran d'ordinateur. Pas de mode tablette, pas de HUD de visière, pas de WebXR.
- **Effet sur les autres tâches** : F5 (HUD) et X4 (WebXR) sont retirées. F1 n'a plus de contrainte de 76 px. F7 ne garde plus le HUD utilisable hors ligne. I2 teste la carte et la vue 3D. Le scénario de démo passe à 14 étapes : l'alerte s'acquitte dans le bandeau de F4.
- **Contournement** : aucun, aucune tâche de la vague 1 n'avait démarré.
