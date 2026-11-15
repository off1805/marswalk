# Rapport des écarts du scénario de démo (I2)

Relevé le 15 novembre 2026 en rejouant `docs/scenario-demo.md` dans Chromium sur le site fictif, front construit (`vite build` puis `vite preview`), API neuve sans base. Chaque écart porte un numéro repris dans les tests : une étape bloquée par un écart est marquée `test.fixme("Écart En …")`, et l'audit d'accessibilité tolère les violations listées ici une à une. Corriger un écart, c'est aussi retirer son `fixme` (ou sa ligne de `KNOWN` dans `tests/accessibilite.spec.ts`) pour que le test le vérifie.

## Bilan par étape

| # | Étape | État | Écart |
| --- | --- | --- | --- |
| 1 | Ouvrir Marswalk sur le site | ✓ | |
| 2 | Préréglage « Sécurité » | ✓ | |
| 3 | Cliquer sur le bord des dunes | ✓ après le correctif de E1 | |
| 4 | Zones dangereuses | ✓ | O3, O4 |
| 5 | Objectif scientifique | ◐ objectif par cible seulement | E2 |
| 6 | Planifier trois cibles | ✓ 2,7 s entre la suppression d'une cible et l'affichage des variantes | |
| 7 | Comparer les variantes | ◐ | E4, E5, E6 |
| 8 | Profil de la variante choisie | ✓ profil et tableau synchronisés ; côté carte, voir « Non vérifié » | |
| 9 | Vue 3D | ◐ exagération réglable, survol en panne | E7 |
| 10 | Sortie et astronaute virtuel | ✓ après le correctif C1 | |
| 11 | Obstacle et observation | ✓ après le correctif de E3 | |
| 12 | Éruption solaire | ✓ alerte affichée 0,4 s après sa réception | |
| 13 | Acquitter l'alerte | ✓ | |
| 14 | Retour forcé, carnet en GeoJSON | ✓ | E8 pour la sortie suivante |
| — | Hors ligne (ENF-01) | ◐ indicateur et données en mémoire ; pas de réouverture hors ligne | E9 |
| — | Accessibilité (axe, WCAG 2.1 AA) | ◐ | E10, E11 |

## Corrigé avec ces tests

**C1. La sortie simulée refusait tout plan calculé.** `POST /api/eva` répondait « Plan inconnu » pour tout plan de `POST /api/sites/{site_id}/plans` : le simulateur (A4) ne lisait que `plan-demo`, comme l'annonçait `tasks/change-requests/A4-source-des-plans.md`. Aucune sortie ne pouvait démarrer depuis l'interface, et l'export GeoJSON du plan (X1) échouait de même. Correctif : `get_simulator()` lit d'abord le dépôt de plans de A2 (PR `fix/I2-integration`), avec un test dans `api/tests/a4/test_plans_a2.py`.

**E1 corrigé. Un clic sur la carte interroge le point (étape 3).** La coquille diffuse chaque clic MapLibre par `shared/mapClick.ts` (contournement de `tasks/change-requests/F2-pickmode-map-click.md`, sans toucher au magasin gelé) ; `QueryPanel` s'y abonne en mode interrogation et part de l'habitat du manifeste. Le clic est lu sur MapLibre, donc il passe même au-dessus d'une cible ou d'une zone ; en mode interrogation, F2 ne sélectionne plus la cible cliquée. Vérifié par l'étape 3, qui contrôle aussi la première requête à l'habitat.

**E3 corrigé. Obstacle et observation pendant la sortie (étape 11).** Panneau « Relevés de terrain » (F7), affiché sous « Sécurité » tant qu'une sortie est suivie : « Signaler un obstacle » poste `POST /api/eva/{id}/obstacles` 50 m devant l'astronaute sur son tracé (rayon 6 m) ; « Noter l'observation » poste à la position courante et, sans réseau ou en cas d'échec, passe par `useOfflineQueue().enqueue("addObservation", …)` avec l'identifiant de la sortie. Le rejeu est désormais gardé au niveau du module, pour qu'une opération ne soit pas rejouée par chaque panneau qui utilise la file. Vérifié par l'étape 11, et l'étape 14 contrôle que l'obstacle et l'observation sont dans le carnet GeoJSON.

## Écarts ouverts

Gravité : **critique** = risque pour la sécurité présentée ; **haute** = une étape de la démo ne se joue pas ; **moyenne** = l'étape se joue mais ne montre pas ce que dit le scénario ; **basse** = finition.

### E2. Pas de panneau science du site (étape 5) · moyenne · S1, F2

Le scénario demande un panneau qui justifie le site et les cibles par les données NASA (delta, argiles et carbonates, olivine). L'interface n'affiche que l'objectif de chaque cible dans sa fiche ; `docs/science/jezero.md` n'est repris nulle part.

### E4. Sans chemin possible, le tracé coupe la falaise sans le dire (étapes 7 et 10) · critique · P2, T00 (site fictif)

Sur le site fictif, la falaise du plateau occupe toute la largeur : le Front du delta est inaccessible, A* ne trouve rien et `_plan_segment` revient à la ligne droite « de secours ». Les trois variantes passent alors par une pente de 65°, sans avertissement (`warnings` vide, alors que le code annonce le contraire) et avec « ✓ Retour 90 % ». Pendant la sortie, l'astronaute virtuel franchit la falaise et lève l'alerte « Pente trop forte, 43° ». À faire : (1) P2 signale tout tronçon de secours dans `warnings` et dans `return_check`, ou refuse la cible ; (2) le site fictif ouvre un passage praticable vers le plateau, pour que la démo de CI montre un vrai détour. À vérifier aussi sur Jezero.

### E5. Les trois variantes sont identiques (étape 7) · haute · P2, I1

Même tracé, même distance, même durée pour « plus sûre », « plus rapide » et « science » sur le site fictif, y compris sur les tronçons atteignables. E4 en explique une partie, pas tout. À revoir avec les poids réglés par I1.

### E6. Les explications ne disent pas la raison du détour (étape 7) · moyenne · P1, P2, F2

Le scénario attend « contourne une pente de 24° ». L'interface affiche les termes du coût de la cellule du milieu du tronçon : « temps de traversée 2.36 s (Tobler 0,38 g × facteur sol) → contribution 1.181 · R=0.000 … ». À faire : une phrase par tronçon tirée de l'écart au tracé direct (pente évitée, obstacle contourné, zone pénalisée).

### E7. Le survol 3D s'arrête aussitôt lancé (étape 9) · moyenne · F6

`useTerrain3dData` reconstruit `activeProfile` à chaque rendu ; l'effet de `useFlyover` qui remet le survol à zéro « quand l'itinéraire change » se déclenche donc à chaque rendu et repasse `playing` à faux. Correctif d'une ligne : `useMemo` sur `activeProfile`.

### E8. Après l'éruption, toute nouvelle sortie s'arrête sur place (après l'étape 14) · haute · A3, A4

Les alertes danger levées par le scénario `solar-event` restent actives (sans sortie rattachée) après l'arrêt du scénario, même acquittées, alors que le débit de dose est revenu à 16 µSv/h. Toute sortie lancée ensuite se termine en une dizaine de secondes sans avoir avancé (0 m). Seul un redémarrage de l'API rétablit la démo. À faire : lever les alertes quand la condition disparaît (`alert_cleared`) et ne forcer le retour que sur les alertes de la sortie en cours ; L1 en aura besoin pour sa commande de réinitialisation.

### E9. Pas de service worker : l'application ne se rouvre pas hors ligne (ENF-01) · haute · F7

`web/src/features/offline/vite.ts` charge `vite-plugin-pwa` par `require`, qui n'existe pas dans la configuration Vite en ESM ; l'erreur est avalée par le `catch` et le greffon n'est jamais ajouté. Le build ne produit ni `sw.js` ni manifeste, rien n'est mis en cache. L'indicateur réseau et les données déjà chargées tiennent, mais un rechargement sans réseau donne une page vide. À faire : `import { VitePWA } from "vite-plugin-pwa"` en tête de fichier.

### E10. Couleurs d'état écrites en texte trop peu contrastées · moyenne · T00 (jetons), F2, F3, F4

Le vert « Normal » #009e73, l'orange #e69f00 et le vermillon #d55e00 servent de couleur de texte. Rapport de contraste : 4,45:1 sur le thème sombre, 2,3 à 3,9:1 sur le thème « plein soleil », au lieu de 4,5:1. Le thème clair, prévu pour la lecture en plein soleil (ENF-06), est le plus touché : jauges du panneau sécurité, « Retour » des variantes, légende du profil, tableau météo. À faire : une variante foncée de chaque couleur d'état pour le texte, la couleur vive restant pour les pastilles et les tracés.

### E11. `aria-label` sur un `div` sans rôle dans la vue 3D · basse · F6

L'élément `.inset-0` du rendu 3D porte un `aria-label` interdit sans rôle. Ajouter `role="img"` (ou retirer l'étiquette, le canevas en porte déjà une).

## Observations sans test dédié

- **O1. Accents manquants dans les étiquettes de la carte.** « Unité à olivine » s'affiche « Unit    olivine » : la police des étiquettes deck.gl n'a pas les caractères accentués (F2).
- **O2. Recalcul local après obstacle à la limite.** `api/tests/a4/test_demo.py` mesure 2,0 s dans le conteneur de cloud (échec à 2 004 ms pour une limite de 2 000 ms, sans lien avec le correctif C1) ; I1 a mesuré 2,9 s sur Jezero pour un objectif de 2 s. Vert dans la CI GitHub.
- **O3. Zones interdites en vermillon, pas en rouge.** Le scénario dit « rouge » ; la palette pour daltoniens utilise le vermillon #d55e00 avec l'icône ⛔. Choix défendable, à aligner dans le texte du scénario.
- **O4. Cause des zones toujours « pente ».** `GET /hazards` ne renvoie que des zones de cause `slope` sur le fictif ; les ruptures de pente et les obstacles ne sont pas cités comme cause.
- **O5. Tout l'état de l'API vit en mémoire.** Cibles, plans, sorties et alertes ne passent pas par PostGIS : un redémarrage efface tout, et deux processus ne partagent rien. Les tests partent donc d'une API neuve à chaque passage ; L1 devra en tenir compte.
- **O6. `uv.lock` pas à jour.** `uv run` sans `--frozen` le réécrit (ajout de matplotlib et de ses dépendances). La CI utilise `--frozen` et n'est pas touchée.

## Non vérifié automatiquement

- La synchronisation du profil avec la carte (étape 8) : le repère est dessiné dans le canevas WebGL. Les tests vérifient le profil et le tableau des tronçons ; le repère sur la carte reste à regarder à l'œil.
- Le rendu visuel des couches, des tracés et de la 3D : les tests vérifient que les canevas s'affichent et que les données arrivent, pas l'image.
- Jezero : les tests tournent sur le site fictif dans la CI. Ils se lancent sur Jezero avec `E2E_SITE=jezero` sur une machine où le paquet est installé.
