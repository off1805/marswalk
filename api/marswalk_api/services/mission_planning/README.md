# Service Mission Planning (mission_planning)

Ce module implémente la planification de missions, la gestion des cibles scientifiques, le calcul des variantes d'itinéraires et l'évaluation des zones de risques (précédemment étiqueté jalon A2).

## Architecture & SOLID

- **Single Responsibility Principle (SRP)** :
  - `ITargetRepository` / `InMemoryTargetRepository` : Persistance CRUD des cibles et waypoints.
  - `IPlanRepository` / `InMemoryPlanRepository` : Persistance des plans de sortie et sélection de variantes.
  - `ISafetySettingsRepository` : Persistance et lecture des seuils de sécurité de l'astronaute.
  - `PlanComputationService` : Orchestration de la recherche d'itinéraires optimisés et de l'évaluation des consommables via `marswalk_planner`.
  - `HazardService` : Génération des masques et polygones de danger.
- **Open/Closed Principle (OCP)** :
  - Le patron Dépôt (Repository) permet de brancher directement une implémentation PostGIS sans aucune modification dans les routeurs ou les services métier.
- **Liskov Substitution Principle (LSP)** :
  - `InMemoryTargetRepository` et toute future implémentation `PostGISTargetRepository` respectent fidèlement le contrat `ITargetRepository`.
- **Interface Segregation Principle (ISP)** :
  - Interfaces minimales dédiées par ressource (`ITargetRepository`, `IPlanRepository`, `ISafetySettingsRepository`).
- **Dependency Inversion Principle (DIP)** :
  - Injection de dépendances via FastAPI (`deps.py`).
