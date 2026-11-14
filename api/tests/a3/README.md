# A3 : alertes et temps réel

Code : `api/marswalk_api/services/a3/` (règles, moteur, diffusion, scénarios) et les routeurs `alerts.py`, `conditions.py`, `time.py`, `ws.py`.

## Fonctionnement

- **Règles** (`rules.py`) : débit de dose, météo spatiale et opacité (conditions du site) ; dose cumulée, réserve au retour, point de non-retour, consommables, pente, couverture radio et lumière restante (télémétrie d'une sortie). Seuils de `config/safety.yaml` ; les seuils absents de ce fichier sont des hypothèses réunies en tête de `rules.py` (débit de dose : vigilance à 30 µSv/h, danger à 50 µSv/h ; point de non-retour à 15 min ; coucher du Soleil à 18:00 LMST).
- **Trois niveaux** `info`, `caution`, `danger`, chacun avec une action conseillée (« Retour à l'abri », « Retour immédiat vers l'habitat », « Ralentir »…).
- **Anti-rebond** (`engine.py`) : `danger` levé dès la première mesure ; `caution` après 2 s ; une alerte reste active tant que la valeur n'est pas 5 % sous son seuil, puis 5 s ; une aggravation remplace l'alerte aussitôt.
- **Hiérarchie** : `GET /api/alerts` trie par gravité, puis les non acquittées, puis les plus récentes.
- **Acquittement** en une action : `POST /api/alerts/{id}/ack` ou, sur le WebSocket, `{"type": "ack", "alert_id": "..."}`.
- **WebSocket** `/ws/eva/{eva_id}` : à la connexion, les conditions et les alertes actives ; ensuite tous les messages de la sortie et du site. Chaque message porte `utc`, `sol` et `lmst` (Mars24, C1).
- **Scénarios** : `POST /api/scenarios/{id}/start?speed=` rejoue le scénario de K1 en accéléré ; toutes les 0,2 s réelles, les conditions à l'instant simulé sont lues et évaluées. `GET /api/time` et les conditions suivent l'instant du scénario.

## Interface pour A4

```python
from marswalk_api.services.a3 import get_service

get_service().ingest_eva(eva)            # après chaque pas : telemetry, budget, alert, alert_cleared
get_service().publish(eva.id, message)   # autre message, par ex. WsRouteUpdated
```

## Limites

- Les alertes sont gardées en mémoire du processus : un redémarrage de l'API les efface, et l'API doit tourner avec un seul processus. La table `alerts` de la migration reste disponible pour une persistance ultérieure.
- Avec le bouchon actuel de K1, les conditions sont constantes et le scénario `solar-event` ne produit pas de pic de dose. Les tests utilisent un fournisseur qui suit le contrat de K1 (pic de dose à 1 200 s). Dès que K1 sera fusionnée, le scénario réel déclenchera l'alerte.

## Tests

`uv run pytest api/tests/a3` : règles et niveaux, anti-rebond (pas de clignotement autour d'un seuil), retour au calme, tri ; scénario `solar-event` qui lève une alerte `danger` « Retour à l'abri » en moins de 1 s sur le WebSocket ; acquittement par REST et par WebSocket ; temps Mars24 ; conditions pendant un scénario ; télémétrie d'une sortie (interface A4).
