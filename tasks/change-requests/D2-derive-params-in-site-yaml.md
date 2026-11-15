# Demande de changement D2 : section `derive:` dans `site.yaml`

**Auteur :** agent D2
**Date :** 2026-11-15
**Statut :** proposé

## 1. Problème

La commande `marswalk derive <site_id>` lit les paramètres des couches dérivées depuis
`cfg["derive"]` dans `site.yaml` du site. Ces paramètres incluent :

```yaml
derive:
  roughness_window_m: 10.0
  obstacle_roughness_threshold_m: 0.4
  obstacle_buffer_m: 2.0
  scarp_threshold_deg: 30.0
  scarp_buffer_m: 10.0
  antenna_height_m: 3.0
  sun_azimuth_deg: 90.0
  sun_altitude_deg: 20.0
  ti_dune_threshold: 170.0
  ti_loose_threshold: 200.0
  ti_mixed_threshold: 270.0
  texture_window_px: 5
  texture_dune_threshold: 5.0
```

Les fichiers `config/sites/fictif/site.yaml` (T00) et `config/sites/jezero/site.yaml`
(D1) ne contiennent pas encore cette section. D2 utilise des valeurs par défaut codées
dans `marswalk_pipeline/derived/__init__.py` (`_DEFAULTS`) lorsque la section est absente.

## 2. Demande

**Propriétaires concernés :**
- `config/sites/fictif/site.yaml` → T00
- `config/sites/jezero/site.yaml` → D1 (puis I1 pour la calibration)

Ajouter la section `derive:` ci-dessus dans les deux fichiers.

**Pour le site fictif (`config/sites/fictif/site.yaml`) :** les valeurs par défaut sont
suffisantes pour les tests. L'ajout est optionnel tant que `_DEFAULTS` est en place.

**Pour le site Jezero (`config/sites/jezero/site.yaml`) :** la section `derive:` est
déjà dans la version D1 locale (non fusionnée). I1 devra calibrer les valeurs
`obstacle_roughness_threshold_m`, `obstacle_buffer_m` et `antenna_height_m` sur les
données réelles.

## 3. Impact sur les autres tâches

- **D2** : contourne avec `_DEFAULTS` (aucune régression).
- **D1** : son `site.yaml` local contient déjà la section ; aucun travail supplémentaire.
- **I1** : devra ajuster les seuils lors de la calibration sur Jezero.
- **P1** : pourrait lire `derive.obstacle_roughness_threshold_m` pour la cohérence des
  seuils entre D2 et P1 — à examiner lors de l'intégration I1.

## 4. Contournement actuel

`marswalk_pipeline/derived/__init__.py` contient un dictionnaire `_DEFAULTS` avec toutes
les valeurs par défaut. Tant que la section `derive:` est absente, ces valeurs s'appliquent.
Les tests D2 passent sans la section dans les configs de site.
