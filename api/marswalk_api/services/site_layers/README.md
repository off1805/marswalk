# Service Site & Layers (site_layers)

Ce module implémente les services de catalogage de sites martiens, de distribution des tuiles cartographiques et d'interrogation de points (précédemment étiqueté jalon A1).

## Architecture & SOLID

- **Single Responsibility Principle (SRP)** :
  - `SiteCatalogService` : Gestion de l'inventaire des sites, manifestes, préréglages et couches vectorielles.
  - `PointQueryService` : Interrogation multicouche au sol et calcul du temps de retour le plus court.
  - `TileService` : Validation et distribution des tuiles statiques avec en-têtes HTTP de mise en cache.
- **Open/Closed Principle (OCP)** :
  - L'interface `ISiteDataSource` permet d'ajouter de nouvelles sources de données (ex: flux direct AWS PDS, COG distant via HTTP, etc.) sans modifier les services ou les routeurs.
- **Liskov Substitution Principle (LSP)** :
  - `PackageSiteDataSource` et `MockSiteDataSource` implémentent fidèlement le contrat `ISiteDataSource`.
- **Interface Segregation Principle (ISP)** :
  - Interfaces distinctes et modulaires (`ISiteCatalogService`, `IPointQueryService`, `ITileService`, `ISiteDataSource`).
- **Dependency Inversion Principle (DIP)** :
  - Les routeurs dépendent d'abstractions injectées via les dépendances FastAPI (`deps.py`).
