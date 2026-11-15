# F4 : bandeau d'alertes dans la vue 3D

- **Champ :** `web/src/app/Layouts.tsx`, `Terrain3dLayout`.
- **Demande :** rendre `<Slot name="top-banner" />` sous la `TopBar` de la vue 3D, comme
  dans `MapLayout`.
- **Raison :** le bandeau d'alertes de F4 (et sa connexion WebSocket) vit dans `top-banner`.
  Dans la vue 3D, aucun emplacement n'est rendu : une alerte `danger` reçue pendant que
  l'astronaute regarde la 3D n'apparaît pas (EF-08, ENF-08).
- **Effet sur les autres tâches :** aucun. Seul F4 utilise `top-banner` aujourd'hui ; F6 n'a
  rien à changer.
- **Contournement dans F4 :** aucun possible sans toucher à la coquille.
