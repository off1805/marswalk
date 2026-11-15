# Conditions martiennes et scénarios (K1)

Ce module implémente le package Python `marswalk_conditions` dédié à la simulation, la prévision et le rejeu des conditions environnementales martiennes (météo atmosphérique MEDA, rayonnement cosmique et éruptions solaires RAD, météo spatiale DONKI).

## Architecture & Principes SOLID

- **Single Responsibility Principle (SRP)** :
  - `MedaClimatologyEngine` : Modèle physique et sinusoïdal des cycles diurnes de température, pression, vent et UV sur Jezero.
  - `HistoricalProvider` : Fourniture des séries chronologiques historiques MEDA / RAD.
  - `ScenarioProvider` & `ScenarioManager` : Moteur d'exécution des scénarios accélérés et reproductibles (dont `solar-event`).
  - `LiveProvider` & `DonkiClient` : Gestion du flux direct DONKI et résilience hors-ligne.
- **Open/Closed Principle (OCP)** :
  - Les interfaces `IMedaRadSource`, `ISpaceWeatherSource` et `ICacheStore` permettent d'ajouter de nouvelles sources de données (ex: lecture de tables Parquet PDS, API REST tierce) sans modifier les fournisseurs.
- **Liskov Substitution Principle (LSP)** :
  - Tous les fournisseurs implémentent fidèlement le protocole `ConditionsProvider`.
- **Interface Segregation Principle (ISP)** :
  - Séparation nette entre `ConditionsProvider`, `IMedaRadSource`, `ISpaceWeatherSource` et `ICacheStore`.
- **Dependency Inversion Principle (DIP)** :
  - Les fournisseurs dépendent de protocoles abstraits plutôt que de clients concrets ou de fichiers sur disque.

## Modes de fonctionnement

1. **`historical`** :
   - Rejoue les conditions météorologiques MEDA (température diurne de -75°C à -18°C, pression semi-diurne autour de 845 Pa, vent thermique d'après-midi, UV solaire) et débit de dose cosmique nominal (~10 µSv/h).
2. **`scenario` (`solar-event`)** :
   - Rejoue l'événement solaire majeur (fondé sur l'événement de mai 2024 observé par Curiosity/RAD).
   - Déclenche un pic de dose critique supérieur à 1 000 µSv/h entre $t=1200$s et $t=2400$s avec alerte `storm`, entraînant les alertes de sécurité requises pour la démo.
3. **`live`** :
   - Client connecté à la météo spatiale NASA DONKI.
   - En cas d'absence de réseau (mode autonome / hors-ligne ENF-01), bascule immédiatement sur le cache local en retournant la dernière mesure avec son horodatage `cached_at`.

## Utilisation

```python
from datetime import datetime, UTC
from marswalk_conditions import get_provider, list_scenarios

# 1. Mode historique
prov_hist = get_provider("historical")
now = datetime.now(UTC)
current_cond = prov_hist.current(now)
forecast_12h = prov_hist.forecast(now, hours=12)

# 2. Mode scénario (solar-event)
prov_scen = get_provider("scenario", scenario_id="solar-event")
cond_at_peak = prov_scen.current(now)

# 3. Mode direct avec cache
prov_live = get_provider("live")
live_cond = prov_live.current(now)
```
