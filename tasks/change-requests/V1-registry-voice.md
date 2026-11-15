# Demande de changement V1 : ajout de l'assistant vocal dans le registre

**Date :** 2026-11-15
**Tâche :** V1 — Assistant vocal
**Sujet :** Enregistrement de la feature `voice` dans `web/src/app/registry.ts` (gelé)

## Problème

`registry.ts` (gelé, T00) liste toutes les features dès le départ. La feature V1 n'y figure pas car elle n'était pas prévue dans le contrat initial.

## Solution demandée

Ajouter dans `registry.ts` :
```typescript
import { feature as voice } from "@/features/voice";
// dans le tableau registry :
voice, // V1
```

## Contournement dans V1

En attendant, V1 utilise `setup()` (prévu dans le contrat `Feature`) pour s'auto-initialiser au démarrage de `main.tsx`. Le bouton micro est un composant autonome monté directement via un portail React dans `setup()`, sans passer par le slot `map-overlay`. Cela fonctionne mais perd le tri par `order` du slot — le bouton apparaît en dernier.

## Effet sur les autres tâches

Aucun : les autres features ne lisent pas le registre pour s'initialiser.
