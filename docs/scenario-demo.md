# Scénario de démo

Ce scénario est le critère d'acceptation commun de Marswalk : chaque tâche le rend possible en partie, et I2 le rejoue de bout en bout dans l'intégration continue. Il se déroule d'abord sur le site fictif (`fixtures/sites/fictif`, centré sur le cratère Jezero), puis sur Jezero après I1. Il dure moins de 3 minutes en accéléré (A4).

Rôles : l'opérateur de l'habitat travaille sur le grand écran (`/`), l'astronaute sur la tablette (`/tablet`) puis sur le HUD de visière (`/hud`).

| # | Étape | Ce que l'on voit | Tâches |
| --- | --- | --- | --- |
| 1 | Ouvrir Marswalk sur le site | La carte du site s'affiche avec l'imagerie, le nom du site, le sol de mission et l'heure solaire locale | T00, D3, F1, C1, A3 |
| 2 | Choisir le préréglage « Sécurité » | Pente, ruptures de pente et obstacles s'affichent ; chaque couche indique sa source, sa résolution et sa date | F1, D2, A1 |
| 3 | Cliquer sur le bord des dunes | Le panneau d'interrogation donne altitude, pente, classe de sol, inertie thermique et minéralogie, avec incertitude et temps de retour vers l'habitat | A1, F1, P3 |
| 4 | Afficher les zones dangereuses | Les zones interdites (rouge, icône « interdit ») et pénalisées (orange) apparaissent ; la falaise du front du delta et le bord du cratère sont interdits | P1, A2, F4 |
| 5 | Lire l'objectif scientifique | Le panneau science justifie le site et les cibles par les données NASA (delta, argiles et carbonates, olivine) | S1, F2 |
| 6 | Planifier trois cibles : Front du delta, Unité à olivine, Bord des dunes | Les cibles se posent sur la carte ; le plan se calcule en moins de 5 s | A2, F2, P2 |
| 7 | Comparer les variantes « plus sûre », « plus rapide » et « science » | Trois tracés différents, chacun avec ses totaux et la raison de ses détours (« contourne une pente de 24° ») ; aucune variante n'est imposée | P2, P1, F2 |
| 8 | Examiner le profil de la variante choisie | Altitude, pente et durée par tronçon ; survoler le profil déplace un repère sur la carte et inversement ; la réserve au retour et le point de non-retour sont affichés | P3, A2, F3 |
| 9 | Voir le site en 3D | Survol du terrain avec exagération verticale réglable | D3, F6 |
| 10 | Lancer la sortie et l'astronaute virtuel en accéléré | La position avance le long du tracé ; les consommables et la dose se mettent à jour par WebSocket | A4, A3, F4 |
| 11 | Passer au HUD | Cinq informations au plus : cap, prochaine cible, réserve, temps avant le point de non-retour, alerte | F5 |
| 12 | Signaler un obstacle et noter une observation | Le tronçon se recalcule localement en moins de 2 s ; l'observation part au carnet, même hors ligne | A4, P2, F7, X1 |
| 13 | Éruption solaire simulée (scénario `solar-event`) | Le débit de dose monte ; une alerte `danger` « retour à l'abri » arrive en moins de 1 s, avec icône, texte et action conseillée | K1, A3, F4, F5 |
| 14 | Acquitter l'alerte au HUD (touche ou commande vocale) | L'alerte est acquittée en une action, sans Internet | F5, A3 |
| 15 | Retour forcé | L'itinéraire est recalculé vers l'habitat (`route_updated`) ; la sortie se termine et le carnet de terrain s'exporte en GeoJSON | A4, P2, P3, X1 |

## Données de la démo

- Site fictif : habitat au centre, quatre cibles (Front du delta, Bord des dunes, Unité à olivine, Chaos de blocs), décrites dans `config/sites/fictif/targets-seed.geojson`.
- Scénario de conditions : `solar-event`, rejeu d'un événement à particules solaires mesuré au sol par RAD (Curiosity, mai 2024 ; date et dose à vérifier par K1 dans le PDS). Perseverance n'emporte pas de RAD : la dose est transposée à Jezero et la transposition est dite dans le pitch.
- Les exemples de `contracts/examples/` montrent l'état attendu après l'étape 13 (plan `plan-demo`, sortie `eva-demo`, alerte `alert-1`).
