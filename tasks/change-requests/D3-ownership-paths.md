# Demande de changement : ajout des chemins D3 hors-périmètre dans ownership.yaml

**Tâche demandeuse :** D3 — Paquet de site  
**Fichier cible :** `tasks/ownership.yaml`  
**Propriétaire :** T00

## Contexte

La branche `task/D3-site-package` modifie trois fichiers hors du périmètre D3 actuel.
La justification détaillée figure dans `tasks/change-requests/D3-out-of-scope.md`.
Le contrôle d'ownership en CI échoue tant que ces chemins ne sont pas listés dans
`tasks.D3.paths`.

## Modification demandée

Dans la section `tasks.D3.paths` de `tasks/ownership.yaml`, ajouter :

```yaml
- D3_REPORT.md
- Makefile
- config/sites/jezero/site.yaml
```

## Justification (résumé)

- **`D3_REPORT.md`** : rapport de livraison D3 à la racine, artefact de documentation sans
  impact fonctionnel (copie identique dans `pipeline/marswalk_pipeline/package/D3_REPORT.md`).
- **`Makefile`** : la cible `make site SITE=jezero` (enchaînement ingest → derive → package)
  est un critère d'acceptation explicite de la fiche D3. La modification est additive
  (ajout d'un garde `ifndef SITE`) et ne touche aucune autre cible.
- **`config/sites/jezero/site.yaml`** : cinq paramètres `derive` ajoutés
  (`ti_dune_threshold`, `ti_loose_threshold`, `ti_mixed_threshold`, `texture_window_px`,
  `texture_dune_threshold`). Clés nouvelles, ignorées par D1 et D2.

## Impact sur les autres tâches

| Fichier | Tâches potentiellement affectées | Évaluation |
|---------|----------------------------------|------------|
| `D3_REPORT.md` | Aucune | Documentation uniquement |
| `Makefile` | T00, toutes | Modification additive et non cassante |
| `config/sites/jezero/site.yaml` | D1, D2 | Clés nouvelles, ignorées si inconnues |
