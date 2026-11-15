# e2e : tests de bout en bout du scénario de démo (I2)

Tests Playwright qui rejouent `docs/scenario-demo.md` dans l'interface web, la carte et la vue 3D, plus un test hors ligne et un contrôle d'accessibilité automatique (axe-core). Les écarts trouvés sont dans [`ECARTS.md`](ECARTS.md).

## Lancer

Prérequis : `make install` à la racine (Python avec uv, front avec pnpm).

```bash
cd e2e
pnpm install --ignore-workspace
pnpm exec playwright install chromium   # une fois
pnpm test                                # un passage
pnpm test:3x                             # trois passages de suite, chacun sur une API neuve
pnpm report                              # rapport HTML du dernier passage
```

Playwright lance lui-même l'API (port 8100, sans base) et le front construit servi par `vite preview` (port 4173). Le build de production est nécessaire pour le service worker du mode hors ligne.

| Variable | Effet |
| --- | --- |
| `E2E_SITE=jezero` | Joue le scénario sur Jezero (le paquet doit être installé dans `data/packages/`) |
| `E2E_REUSE=1` | Réutilise une API et un front déjà lancés sur les ports 8100 et 4173 |
| `E2E_SKIP_BUILD=1` | Sert `web/dist` sans le reconstruire |
| `E2E_API_PORT`, `E2E_WEB_PORT` | Autres ports |

L'API garde cibles, plans, sorties et alertes en mémoire : un passage modifie cet état (une cible supprimée, une éruption jouée). `pnpm test:3x` relance donc les serveurs à chaque passage, comme la CI.

## Contenu

| Fichier | Rôle |
| --- | --- |
| `tests/scenario.spec.ts` | Les 14 étapes du scénario, une par test, jouées dans l'ordre sur la même page |
| `tests/hors-ligne.spec.ts` | Coupure du réseau en cours d'usage, réouverture sans réseau (ENF-01) |
| `tests/accessibilite.spec.ts` | axe-core, WCAG 2.1 A et AA, carte et 3D, thèmes sombre et plein soleil (ENF-06) |
| `tests/helpers.ts` | Ouverture de l'application, remise des cibles de départ, position d'un point à l'écran |
| `ECARTS.md` | Rapport des écarts : ce qui ne passe pas, pourquoi, et qui le corrige |

## Écarts et `fixme`

Une étape que l'application ne permet pas encore est marquée `test.fixme(true, "Écart En …")` : elle est sautée, le reste du scénario continue et le rapport la montre. Le corps du test décrit déjà ce qu'il faut vérifier. Quand l'écart est corrigé, retirer la ligne `fixme` et relancer.

L'audit d'accessibilité tolère les violations listées dans `KNOWN` (une règle et un motif par écart) et échoue sur toute autre. Il joint le rapport axe complet de chaque vue au résultat.

## Mesures relevées par les tests

Chaque passage note dans le rapport HTML :

- la durée entre la modification des cibles et l'affichage des trois variantes (EF-05, limite 5 s) ;
- le délai entre la réception d'une alerte par WebSocket et son affichage (limite 1 s) ;
- les débits de dose reçus pendant l'éruption simulée.

## Intégration continue

Le job « Scénario de démo » (`.github/workflows/e2e.yml`) construit le front une fois, puis joue la suite trois fois de suite, chacune sur une API neuve, sans nouvel essai. Les rapports HTML des trois passages sont joints au job.
