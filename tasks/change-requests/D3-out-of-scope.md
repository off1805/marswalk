# Demande de périmètre étendu — D3

**Tâche :** D3 — Paquet de site  
**Branche :** `task/D3-site-package`  
**Fichiers concernés :** `D3_REPORT.md`, `Makefile`, `config/sites/jezero/site.yaml`

---

## Raison

### `D3_REPORT.md` (racine)

Rapport de livraison D3 placé à la racine du dépôt pour visibilité immédiate lors de la revue.
Une copie identique existe dans `pipeline/marswalk_pipeline/package/D3_REPORT.md` (dans le
périmètre D3). La version racine est un artefact de documentation, sans impact fonctionnel.

### `Makefile`

La cible `site` (enchainement `ingest → derive → package`) est un critère d'acceptation
explicite de la fiche D3 : *"Commande `make site SITE=jezero` enchaîne ingest → derive →
package"*. La modification ajoute uniquement un garde `ifndef SITE … error` et améliore le
commentaire de la cible existante. Aucune autre cible n'est touchée.

### `config/sites/jezero/site.yaml`

Cinq paramètres `derive` ajoutés dans la section existante (`ti_dune_threshold`,
`ti_loose_threshold`, `ti_mixed_threshold`, `texture_window_px`, `texture_dune_threshold`).
Ces seuils sont lus par le module D3 lors de la génération des couches `loose_soil` et
`roughness` sur le site Jezero. Sans eux, le pipeline D3 utilise des valeurs par défaut moins
précises. La section `ingest` (périmètre D1) n'est pas modifiée.

---

## Impact sur les autres tâches

| Fichier | Tâches potentiellement affectées | Évaluation |
|---------|----------------------------------|------------|
| `D3_REPORT.md` | Aucune | Documentation uniquement |
| `Makefile` | T00, toutes | Modification additive et non cassante |
| `config/sites/jezero/site.yaml` | D1 (lit `ingest:`), D2 (lit `derive:`) | Les clés ajoutées sont nouvelles ; D1 et D2 ignorent les clés inconnues |
