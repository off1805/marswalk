# F4 — Panneau sécurité et conditions

Bandeau d'alertes, jauges, comptes à rebours, météo et météo spatiale, seuils et horloge
martienne (EF-08, EF-11, ENF-06, ENF-08, ENF-11).

## Emplacements

| Emplacement | Ordre | Composant | Contenu |
|---|---|---|---|
| `top-banner` | 10 | `AlertBanner` | Alertes actives, classées (non acquittées, danger, attention, information, plus récente), bouton « Acquitter ». Porte la connexion WebSocket. |
| `right` | 5 | `SafetyPanel` | Horloge (sol, LMST, UTC), point de non-retour, coucher du Soleil, réserve au retour, oxygène, batterie, eau, dose ; démarrage d'une sortie simulée. |
| `right` | 30 | `ConditionsPanel` | Soleil (météo spatiale), débit de dose, opacité, température, pression, vent, UV, source et cache ; prévisions 12 h ; rejeu d'un scénario. |
| `right` | 35 | `ThresholdsPanel` | Seuils de `SafetySettings` (pente, réserve, poussière, dose, éclairement, radio), avec contrôle de cohérence. |

## Fichiers

| Fichier | Rôle |
|---|---|
| `index.ts` | Export `feature` |
| `useSafetyStream.ts` | WebSocket `/ws/eva/{eva_id}` d'A3, reconnexion avec attente croissante (≤ 10 s) |
| `queries.ts` | Requêtes et mutations TanStack Query, sous les clés de `shared/queryKeys.ts` |
| `safetyStore.ts` | Zustand local : télémétrie, budget, ancre d'horloge, état de la liaison |
| `thresholds.ts` | Niveaux des jauges, tri des alertes, horloge, mises en forme, validation des seuils |
| `ui.tsx` | `Gauge`, `Countdown`, `LevelTag`, `useNow` |
| `safety.test.tsx` | Tests (règles, messages, critères d'acceptation) |

## Flux de données

- **Alertes** : `GET /api/alerts?eva_id=` dans le cache `alerts(evaId)`, relu toutes les 5 s
  quand le WebSocket n'est pas ouvert. Un message `alert` est inséré dans ce cache dès sa
  réception, `alert_cleared` l'en retire. L'acquittement (`POST /api/alerts/{id}/ack`) est
  optimiste : l'alerte passe à « ✓ Acquittée » sans attendre la réponse.
- **Conditions** : `GET .../conditions/current` (30 s) et les messages `conditions`, dans le
  cache `conditionsCurrent(siteId)`, partagé avec les autres vues.
- **Télémétrie et budget** : messages `telemetry` et `budget`, sinon `GET /api/eva/{id}`
  (5 s hors liaison), sinon les valeurs prévues par la variante active du plan.
- **Horloge** : ancrée sur `GET /api/time` ou sur la dernière enveloppe WebSocket (la plus
  récente des deux), puis avancée localement à vitesse réelle (une heure martienne vaut
  3 698,97 s). Pendant un scénario, `/api/time` donne l'instant du scénario.
- **Seuils** : `PUT .../settings`, puis les zones dangereuses et les plans sont relus.

## Niveaux

Les jauges passent à « Attention » et « Danger » aux mêmes seuils que le moteur d'alertes
d'A3 (`api/marswalk_api/services/a3/rules.py`) : consommables et réserve sous le minimum
plus 10 points puis sous le minimum ; dose à 80 % puis 100 % du maximum ; débit de dose à 30
puis 50 µSv/h ; opacité à 80 % puis 100 % du maximum ; point de non-retour à 15 min puis
atteint ; coucher du Soleil (18 h LMST) à 1 h puis 30 min martiennes. Chaque niveau s'affiche
avec une icône et un texte (✓ Normal, ⓘ Information, ▲ Attention, ⛔ Danger), jamais la
couleur seule.

## Critères d'acceptation

| Critère | Démonstration |
|---|---|
| Une alerte `danger` reçue par WebSocket s'affiche en moins de 1 s | `safety.test.tsx`, « affiche une alerte danger … en moins de 1 s » : faux WebSocket, chronométrage entre l'émission et l'apparition du `role="alert"` |
| Elle se traite en deux actions au plus | Même test : un clic sur « Acquitter » suffit |
| La couleur n'est jamais le seul indice | Même test (⛔, « Danger », titre, action) ; tests des jauges et de la météo spatiale (icône et libellé) |

## Limites connues

- La vue 3D (`/3d`) n'affiche aucun emplacement de la coquille : le bandeau d'alertes n'y
  est pas visible. Voir `tasks/change-requests/F4-bandeau-vue-3d.md`.
- Le coucher du Soleil est fixé à 18 h LMST, comme dans A3 ; un calcul selon la saison
  (`ls_deg`) et la latitude reste à faire côté serveur.
