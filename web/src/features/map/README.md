# F1 - Carte et Couches

Ce module implémente la fonctionnalité **F1** de Marswalk : la gestion cartographique interactive 2D (MapLibre + deck.gl), le panneau de couches et l'interrogation au sol.

## Architecture & SOLID

- **Single Responsibility Principle (SRP)** :
  - `LayerPanel` : Contrôle de la visibilité, de l'opacité et de la légende de chaque couche.
  - `QueryPanel` : Interrogation au sol en un point et affichage des valeurs multicouches (EF-07).
  - `MarsScaleBar` : Barre d'échelle exclusivement martienne calculée sur l'ellipsoïde Mars 2000 (Règle R3).
  - `LegendView` : Composant dédié au rendu visuel des légendes continues et catégorielles.
  - `getMapSources` : Fonction pure transformant l'état Zustand en sources MapLibre.
- **Open/Closed Principle (OCP)** :
  - L'affichage des couches est 100 % dynamique et piloté par les métadonnées du manifeste du site (`SiteManifest.layers`). L'ajout d'une couche dans `site.yaml` l'affiche automatiquement sans modifier de code React.
- **Liskov Substitution Principle (LSP)** :
  - Fonctionne de manière identique avec le serveur réel FastAPI ou avec les mocks MSW (`pnpm dev:mock`).
- **Interface Segregation Principle (ISP)** :
  - Interfaces TypeScript strictes et minimales définies dans `types.ts`.
- **Dependency Inversion Principle (DIP)** :
  - Les composants dépendent des abstractions de l'état partagé (`useShared`), du client HTTP généré et des hooks TanStack Query.

## Règles géographiques et exigences couvertes

- **R3 & ENF-11** : L'échelle de la carte utilise le rayon de Mars 2000 (`3 396 190 m`) via `metersPerPixel`, jamais de projection terrestre.
- **EF-01 & EF-02** : Gestion indépendante d'au moins 4 couches avec réglage d'opacité.
- **EF-07** : Mode interrogation de point avec affichage de toutes les couches, incertitudes et temps de retour.
- **ENF-06** : La couleur n'est jamais le seul indicateur : les alertes et statuts dégradés comportent toujours une icône et un libellé textuel accessible.
- **ENF-07** : Avertissement visible ("Dégradé") lorsqu'une couche est en statut dégradé.
