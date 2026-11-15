# Demande de changement G1 : servir les vignettes du paquet

**Auteur :** agent G1
**Date :** 2026-11-14
**Statut :** proposé

- **Champ ou route** : nouvelle route statique `GET /sites/{site_id}/thumbs/{name}` (A1, à côté des tuiles), au contrat OpenAPI.
- **Raison** : le pipeline de G1 enregistre les vignettes dans le paquet (`thumbs/<image_id>.jpg`, déjà copiées par D3), et l'index les référence par le chemin relatif `thumbs/<image_id>.jpg`. Aucune route ne les sert aujourd'hui. Le front affiche donc la vignette distante du JPL (`thumb_url`), qui manque hors ligne (F7).
- **Proposition** : servir `site.root / "thumbs" / name` avec `image/jpeg` et le même cache que les tuiles. Le front de G1 résoudra alors `thumb` en `/sites/{site_id}/thumbs/<image_id>.jpg`, et F7 pourra précharger ces vignettes avec le paquet.
- **Effet sur les autres tâches** : A1 ajoute la route, T00 régénère le contrat (`contrats-v3`), F7 ajoute le motif au préchargement.
- **Contournement** : en attendant, `thumbSrc` prend `thumb_url`. Les vignettes s'affichent en ligne, pas hors ligne.
