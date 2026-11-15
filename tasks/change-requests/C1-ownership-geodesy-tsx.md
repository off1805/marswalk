# Demande de changement C1 — ownership pour `geodesy-scale-bar.tsx`

**Auteur :** agent C1  
**Date :** 2026-11-14  
**Statut :** proposé

## Contexte

La fiche C1 (`taches-agents.md` §10) prévoit :

> barre d'échelle martienne réutilisable (composant dans `web/src/shared/`)

Le composant React correspondant (`geodesy-scale-bar.tsx`) doit résider dans
`web/src/shared/`. Or la règle d'ownership de C1 dans `tasks/ownership.yaml`
liste :

```yaml
- web/src/shared/geodesy*.ts
```

Le glob `geodesy*.ts` ne couvre pas les fichiers `.tsx`. Le fichier
`geodesy-scale-bar.tsx` est donc hors périmètre avec l'ownership actuel.

## Demande

Modifier `tasks/ownership.yaml`, section `C1.paths`, en remplaçant :

```yaml
- web/src/shared/geodesy*.ts
```

par :

```yaml
- web/src/shared/geodesy*.ts
- web/src/shared/geodesy*.tsx
```

## Effet sur les autres tâches

Aucun effet direct : personne d'autre ne revendique `web/src/shared/geodesy*`.

## Contournement actuel

La logique pure de barre d'échelle (`computeScaleBar`, `formatMarsDistance`,
`ScaleBarResult`) est intégrée directement dans `geodesy.ts` (fichier couvert
par C1). Elle est testable sans React et réutilisable par n'importe quel rendu
(SVG, canvas, React).

Le composant React `<MarsScaleBar>` sera ajouté dans `geodesy-scale-bar.tsx`
dès l'acceptation de cette demande et la mise à jour de `ownership.yaml`.
