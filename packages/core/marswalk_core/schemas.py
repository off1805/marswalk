"""Modèles Pydantic de Marswalk : source de vérité des contrats (contrats-v1).

Ce fichier est gelé après la fusion de T00. Tout changement passe par
``tasks/change-requests/`` (voir ``taches-agents.md`` section 9).

Conventions (``taches-agents.md`` section 4) :
- R1 : tout calcul se fait en mètres dans le système d'analyse du site (``analysis_crs``).
- R2 : toute coordonnée échangée (API, GeoJSON) est en longitude et latitude
  planétocentriques, longitudes est de -180 à 180, référentiel Mars 2000 (IAU_2015:49900).
  Un point s'écrit ``[lon, lat]`` comme en GeoJSON.
- Les durées sont en secondes, les distances en mètres, les doses en microsieverts,
  l'oxygène en kilogrammes et l'énergie en wattheures.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

CONTRACTS_VERSION = "contrats-v1"
SCHEMA_VERSION = "1.0"

MARS_2000_RADIUS_M = 3_396_190.0
"""Rayon de la sphère Mars 2000 (IAU_2015:49900)."""

MARS_MEAN_RADIUS_M = 3_389_500.0
"""Rayon moyen de Mars."""

POSTGIS_MARS_SRID = 949900
"""SRID personnalisé PostGIS pour Mars 2000 géographique (IAU_2015:49900)."""


class Model(BaseModel):
    """Base commune : champs inconnus refusés, noms exacts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------------------
# Géométrie
# ---------------------------------------------------------------------------


class LonLat(NamedTuple):
    """Point en degrés planétocentriques est, sérialisé ``[lon, lat]``."""

    lon: float
    lat: float


Lon = Annotated[float, Field(ge=-180.0, le=180.0)]
Lat = Annotated[float, Field(ge=-90.0, le=90.0)]


class PointGeometry(Model):
    type: Literal["Point"] = "Point"
    coordinates: LonLat


class LineStringGeometry(Model):
    type: Literal["LineString"] = "LineString"
    coordinates: list[LonLat]


class PolygonGeometry(Model):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[LonLat]]


class MultiPolygonGeometry(Model):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[LonLat]]]


Geometry = Annotated[
    PointGeometry | LineStringGeometry | PolygonGeometry | MultiPolygonGeometry,
    Field(discriminator="type"),
]


class Feature(Model):
    type: Literal["Feature"] = "Feature"
    id: str | int | None = None
    geometry: Geometry | None
    properties: dict[str, Any] = Field(default_factory=dict)


class FeatureCollection(Model):
    """FeatureCollection GeoJSON en coordonnées Mars 2000 (dérogation assumée à la RFC 7946)."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature] = Field(default_factory=list)
    crs_note: str = "IAU_2015:49900 (Mars 2000, planétocentrique, longitudes est)"


# ---------------------------------------------------------------------------
# Paquet de site et couches (section 5)
# ---------------------------------------------------------------------------

LayerId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")]

KNOWN_LAYER_IDS: tuple[str, ...] = (
    "hirise_vis",
    "ctx_vis",
    "dem",
    "dem_mola",
    "slope",
    "roughness",
    "hillshade",
    "obstacles",
    "scarps",
    "thermal_inertia",
    "loose_soil",
    "crism_minerals",
    "radio_coverage",
    "illumination",
    "return_time",
    "rover_traverse",
    "ground_images",
)
"""Identifiants fixes de la section 5.3. Une nouvelle couche ajoute un identifiant via site.yaml."""


class LayerKind(StrEnum):
    imagery = "imagery"
    dem = "dem"
    derived = "derived"
    thermal = "thermal"
    spectral = "spectral"
    vector = "vector"
    ground = "ground"


class LayerStatus(StrEnum):
    ok = "ok"
    missing = "missing"
    degraded = "degraded"


class LayerSource(Model):
    instrument: str = Field(description="Instrument, ou SYNTHETIC pour le site fictif")
    mission: str
    product_id: str | None = Field(default=None, description="Identifiant du produit PDS")
    url: str | None = None
    note: str | None = None


class Uncertainty(Model):
    value: float | None = Field(default=None, description="Incertitude de mesure")
    unit: str | None = None
    coreg_m: float | None = Field(default=None, description="Incertitude de recalage en mètres")


class LegendStop(Model):
    value: float
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    label: str | None = None


class Legend(Model):
    type: Literal["continuous", "categorical"]
    stops: list[LegendStop]


class TileInfo(Model):
    path: str = Field(description="Gabarit relatif au paquet, par ex. tiles/slope/{z}/{x}/{y}.webp")
    minzoom: int = Field(ge=0, le=24)
    maxzoom: int = Field(ge=0, le=24)
    format: Literal["webp", "png"]
    tile_size: int = 256


class LayerInfo(Model):
    id: LayerId
    title: str
    kind: LayerKind
    unit: str | None = None
    value_range: tuple[float, float] | None = None
    resolution_m: float | None = None
    acquired: date | None = None
    source: LayerSource
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    legend: Legend | None = None
    cog: str | None = Field(default=None, description="Chemin relatif du COG, par ex. cog/slope.tif")
    tiles: TileInfo | None = None
    vector: str | None = Field(default=None, description="Chemin relatif du GeoJSON")
    status: LayerStatus = LayerStatus.ok
    status_note: str | None = None


class GridInfo(Model):
    resolution_m: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    transform: tuple[float, float, float, float, float, float] = Field(
        description="Transformation affine (a, b, c, d, e, f) au sens de rasterio, en mètres"
    )


class SiteManifest(Model):
    """Contenu de ``manifest.json`` (schéma exporté : contracts/site-manifest.schema.json)."""

    schema_version: str = SCHEMA_VERSION
    site_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    name: str
    bbox: tuple[float, float, float, float] = Field(description="[ouest, sud, est, nord] en degrés")
    analysis_crs: str = Field(description="Chaîne PROJ du système d'analyse (règle R1)")
    grid: GridInfo
    habitat: LonLat
    rover: LonLat | None = None
    mission_epoch_utc: datetime = Field(description="Début du sol 1 de la mission simulée")
    default_preset: str = "safety"
    layers: list[LayerInfo]
    terrain: TileInfo | None = Field(default=None, description="Tuiles terrain-RGB pour la 3D")
    generated_at: datetime | None = None
    generator: str | None = None
    size_bytes: int | None = None


class SiteSummary(Model):
    site_id: str
    name: str
    bbox: tuple[float, float, float, float]
    habitat: LonLat


# ---------------------------------------------------------------------------
# Préréglages d'affichage (config/presets.yaml)
# ---------------------------------------------------------------------------


class LayerViewState(Model):
    visible: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class DisplayPreset(Model):
    id: str
    title: str
    layers: dict[str, LayerViewState]


# ---------------------------------------------------------------------------
# Interrogation de point (EF-07)
# ---------------------------------------------------------------------------


class PointValue(Model):
    layer_id: str
    title: str
    value: float | None
    unit: str | None = None
    label: str | None = Field(default=None, description="Libellé de classe pour une couche catégorielle")
    status: LayerStatus = LayerStatus.ok
    source: LayerSource
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    acquired: date | None = None
    resolution_m: float | None = None


class PointQuery(Model):
    site_id: str
    position: LonLat
    analysis_xy: tuple[float, float] = Field(description="Coordonnées dans le système d'analyse, en m")
    values: list[PointValue]
    return_time_s: float | None = Field(default=None, description="Temps de retour vers l'habitat")


# ---------------------------------------------------------------------------
# Sécurité, coût et combinaison (config/safety.yaml, config/suit.yaml)
# ---------------------------------------------------------------------------


class CostWeights(Model):
    time: float = 1.0
    risk: float = 1.0
    science: float = 0.5


class SafetySettings(Model):
    """Seuils de sécurité et poids du coût. Valeurs par défaut réglées par P1, calibrées par I1."""

    preset: str = "standard"
    max_slope_deg: float = Field(default=20.0, description="Interdit au-delà")
    penalty_slope_deg: float = Field(default=10.0, description="Pénalité forte au-delà")
    max_roughness_m: float = 0.5
    obstacle_buffer_m: float = 2.0
    scarp_buffer_m: float = 10.0
    avoid_loose_soil_class: int = Field(default=3, description="Classe de sol interdite et au-delà")
    require_radio: bool = False
    radio_penalty: float = 2.0
    min_illumination: float = 0.0
    min_reserve_pct: float = Field(default=30.0, description="Réserve minimale au retour, en %")
    max_dust_tau: float = 2.0
    max_dose_usv: float = 1000.0
    degraded_margin_pct: float = Field(
        default=15.0, description="Marge ajoutée quand une couche manque (ENF-07)"
    )
    weights: CostWeights = Field(default_factory=CostWeights)


class SuitModel(Model):
    """Modèle de combinaison et de marche. Valeurs par défaut réglées par P3."""

    name: str = "default"
    mass_total_kg: float = 180.0
    gravity_ms2: float = 3.721
    base_speed_mps: float = 1.0
    max_speed_mps: float = 1.4
    oxygen_capacity_kg: float = 1.2
    oxygen_rate_kg_h: float = 0.08
    battery_capacity_wh: float = 1500.0
    battery_rate_w: float = 150.0
    water_capacity_l: float = 4.0
    water_rate_l_h: float = 0.3
    soil_speed_factor: list[float] = Field(
        default_factory=lambda: [1.0, 0.9, 0.7, 0.5],
        description="Facteur de vitesse par classe de sol 0 à 3",
    )


# ---------------------------------------------------------------------------
# Temps martien (ENF-11)
# ---------------------------------------------------------------------------


class MarsTime(Model):
    utc: datetime
    msd: float = Field(description="Mars Sol Date")
    sol: int = Field(description="Sol de mission, 1 au début de mission_epoch_utc")
    lmst: str = Field(description="Heure solaire moyenne locale, HH:MM:SS")
    lmst_hours: float
    ltst: str | None = Field(default=None, description="Heure solaire vraie locale, HH:MM:SS")
    ls_deg: float | None = Field(default=None, description="Longitude solaire")


class TimeInfo(MarsTime):
    site_id: str
    lon_east: float


# ---------------------------------------------------------------------------
# Conditions (EF-11)
# ---------------------------------------------------------------------------


class SpaceWeatherLevel(StrEnum):
    quiet = "quiet"
    watch = "watch"
    warning = "warning"
    storm = "storm"


class SpaceWeather(Model):
    level: SpaceWeatherLevel = SpaceWeatherLevel.quiet
    event: str | None = None
    source: str | None = None


class Conditions(Model):
    utc: datetime
    sol: int | None = None
    lmst: str | None = None
    mode: Literal["historical", "scenario", "live", "constant"] = "constant"
    temperature_c: float | None = None
    pressure_pa: float | None = None
    wind_mps: float | None = None
    dust_tau: float | None = Field(default=None, description="Opacité atmosphérique")
    uv_index: float | None = None
    dose_rate_usv_h: float | None = Field(default=None, description="Débit de dose, µSv/h")
    space_weather: SpaceWeather = Field(default_factory=SpaceWeather)
    source: str | None = None
    cached_at: datetime | None = Field(default=None, description="Date de la valeur en cache (live)")


class Forecast(Model):
    site_id: str
    generated_at: datetime
    items: list[Conditions]


class ScenarioEvent(Model):
    t_s: float = Field(description="Instant depuis le début du scénario")
    kind: str
    description: str


class Scenario(Model):
    id: str
    title: str
    description: str
    duration_s: float
    events: list[ScenarioEvent] = Field(default_factory=list)


class ScenarioState(Model):
    scenario_id: str | None
    running: bool
    started_at: datetime | None = None
    elapsed_s: float = 0.0
    speed: float = 1.0


# ---------------------------------------------------------------------------
# Cibles (EF-04)
# ---------------------------------------------------------------------------


class TargetKind(StrEnum):
    science = "science"
    waypoint = "waypoint"


class TargetBase(Model):
    name: str
    kind: TargetKind = TargetKind.science
    position: LonLat
    objective: str | None = Field(default=None, description="Objectif scientifique")
    measurement: str | None = Field(default=None, description="Mesure ou prélèvement prévu")
    work_time_s: float = Field(default=900.0, ge=0)
    priority: int = Field(default=2, ge=1, le=3, description="1 haute, 3 basse")


class TargetCreate(TargetBase):
    pass


class TargetUpdate(Model):
    name: str | None = None
    kind: TargetKind | None = None
    position: LonLat | None = None
    objective: str | None = None
    measurement: str | None = None
    work_time_s: float | None = None
    priority: int | None = None


class Target(TargetBase):
    id: str
    site_id: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Itinéraires et plans (EF-05, EF-06)
# ---------------------------------------------------------------------------


class RouteVariant(StrEnum):
    safest = "safest"
    fastest = "fastest"
    science = "science"


class Consumption(Model):
    oxygen_kg: float = 0.0
    battery_wh: float = 0.0
    water_l: float = 0.0
    dose_usv: float = 0.0


class RouteSegment(Model):
    index: int
    from_point: LonLat
    to_point: LonLat
    from_target_id: str | None = Field(description="None pour l'habitat")
    to_target_id: str | None = Field(description="None pour l'habitat")
    distance_m: float
    duration_s: float = Field(description="Temps de marche du tronçon")
    ascent_m: float
    descent_m: float
    max_slope_deg: float
    consumption: Consumption
    work_time_s: float = Field(description="Temps de travail à la cible d'arrivée")


class ProfileSample(Model):
    distance_m: float = Field(description="Distance cumulée")
    position: LonLat
    elevation_m: float | None
    slope_deg: float | None
    time_s: float = Field(description="Temps cumulé, travail aux cibles compris")
    segment_index: int


class RouteTotals(Model):
    distance_m: float
    walk_time_s: float
    work_time_s: float
    duration_s: float
    ascent_m: float
    descent_m: float
    max_slope_deg: float
    consumption: Consumption


class ReturnStatus(StrEnum):
    ok = "ok"
    marginal = "marginal"
    fail = "fail"


class ReturnCheck(Model):
    status: ReturnStatus
    reserve_at_return_pct: float = Field(description="Réserve du consommable limitant au retour")
    limiting_consumable: Literal["oxygen", "battery", "water", "time", "dose"]
    point_of_no_return: LonLat | None = None
    point_of_no_return_time_s: float | None = None
    targets_to_cut: list[str] = Field(
        default_factory=list, description="Cibles à couper pour tenir la réserve"
    )
    message: str | None = None


class SegmentExplanation(Model):
    segment_index: int
    reasons: list[str]


class Route(Model):
    id: str
    variant: RouteVariant
    geometry: LineStringGeometry
    segments: list[RouteSegment]
    profile: list[ProfileSample] = Field(description="Échantillons tous les 5 m")
    totals: RouteTotals
    return_check: ReturnCheck
    explanation: list[SegmentExplanation]
    warnings: list[str] = Field(default_factory=list)


class PlanStatus(StrEnum):
    draft = "draft"
    computed = "computed"
    selected = "selected"
    failed = "failed"


class PlanCreate(Model):
    target_ids: list[str] = Field(min_length=1)
    start: LonLat | None = Field(default=None, description="Départ ; l'habitat si absent")
    return_to: LonLat | None = Field(default=None, description="Arrivée ; l'habitat si absent")
    variants: list[RouteVariant] = Field(
        default_factory=lambda: [RouteVariant.safest, RouteVariant.fastest, RouteVariant.science]
    )
    optimize_order: bool = True
    departure_utc: datetime | None = None


class PlanUpdate(Model):
    selected_route_id: str | None = None
    name: str | None = None


class Plan(Model):
    id: str
    site_id: str
    name: str | None = None
    status: PlanStatus
    created_at: datetime
    departure_utc: datetime | None = None
    start: LonLat
    return_to: LonLat
    target_ids: list[str] = Field(description="Ordre de visite retenu")
    settings: SafetySettings
    suit: SuitModel
    routes: list[Route]
    selected_route_id: str | None = None
    compute_time_ms: float | None = None


# ---------------------------------------------------------------------------
# Alertes (EF-08)
# ---------------------------------------------------------------------------


class AlertLevel(StrEnum):
    info = "info"
    caution = "caution"
    danger = "danger"


class AlertCause(StrEnum):
    slope = "slope"
    radiation = "radiation"
    solar_event = "solar_event"
    dust = "dust"
    consumables = "consumables"
    return_reserve = "return_reserve"
    point_of_no_return = "point_of_no_return"
    off_route = "off_route"
    radio = "radio"
    illumination = "illumination"
    obstacle = "obstacle"
    other = "other"


class Alert(Model):
    id: str
    eva_id: str | None = None
    level: AlertLevel
    cause: AlertCause
    title: str
    message: str
    action: str = Field(description="Action conseillée, par ex. « retour à l'abri »")
    value: float | None = None
    threshold: float | None = None
    unit: str | None = None
    position: LonLat | None = None
    utc: datetime
    sol: int
    lmst: str
    acknowledged: bool = False
    acknowledged_at: datetime | None = None


# ---------------------------------------------------------------------------
# Sorties (EVA)
# ---------------------------------------------------------------------------


class EvaStatus(StrEnum):
    planned = "planned"
    active = "active"
    returning = "returning"
    completed = "completed"
    aborted = "aborted"


class ConsumablesState(Model):
    oxygen_pct: float
    battery_pct: float
    water_pct: float


class EvaCreate(Model):
    plan_id: str
    route_id: str
    crew: list[str] = Field(default_factory=lambda: ["EV1"])
    start_utc: datetime | None = None


class Eva(Model):
    id: str
    site_id: str
    plan_id: str
    route_id: str
    crew: list[str]
    status: EvaStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    position: LonLat
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    distance_done_m: float = 0.0
    elapsed_s: float = 0.0
    consumables: ConsumablesState
    dose_usv: float = 0.0
    next_target_id: str | None = None
    reserve_pct: float | None = None
    time_to_pnr_s: float | None = Field(default=None, description="Temps avant le point de non-retour")
    return_time_s: float | None = None
    active_alert_ids: list[str] = Field(default_factory=list)


class PositionReport(Model):
    position: LonLat
    heading_deg: float | None = None
    speed_mps: float | None = None
    utc: datetime | None = None


class ObservationCreate(Model):
    position: LonLat
    note: str
    photo_url: str | None = None
    target_id: str | None = None
    utc: datetime | None = None


class Observation(ObservationCreate):
    id: str
    eva_id: str
    utc: datetime  # type: ignore[assignment]
    sol: int
    lmst: str


class ObstacleReport(Model):
    position: LonLat
    radius_m: float = Field(default=5.0, gt=0)
    note: str | None = None


class ObstacleResponse(Model):
    obstacle_id: str
    route: Route | None = Field(description="Itinéraire recalculé localement, None si inchangé")
    compute_time_ms: float | None = None


class SimulateRequest(Model):
    speed: float = Field(default=10.0, gt=0, description="Facteur d'accélération du temps")
    scenario_id: str | None = Field(default=None, description="Scénario de conditions à rejouer")


class SimulationState(Model):
    eva_id: str
    running: bool
    speed: float
    scenario_id: str | None = None


# ---------------------------------------------------------------------------
# Carnet de terrain (EF-15)
# ---------------------------------------------------------------------------


class LogbookEntry(Model):
    utc: datetime
    sol: int
    lmst: str
    kind: Literal["start", "target", "observation", "alert", "obstacle", "reroute", "end"]
    text: str
    position: LonLat | None = None
    ref_id: str | None = None


class Logbook(Model):
    eva_id: str
    site_id: str
    entries: list[LogbookEntry]


# ---------------------------------------------------------------------------
# Santé
# ---------------------------------------------------------------------------


class Health(Model):
    status: Literal["ok", "degraded"]
    version: str
    contracts: str = CONTRACTS_VERSION
    database: Literal["ok", "unavailable", "disabled"]
    sites: list[str]


# ---------------------------------------------------------------------------
# Temps réel : WebSocket /ws/eva/{eva_id}
# ---------------------------------------------------------------------------


class TelemetryPayload(Model):
    position: LonLat
    heading_deg: float
    speed_mps: float
    consumables: ConsumablesState
    dose_usv: float
    distance_done_m: float
    elapsed_s: float


class AlertClearedPayload(Model):
    alert_id: str
    reason: str | None = None


class RouteUpdatedPayload(Model):
    reason: str
    route: Route


class BudgetPayload(Model):
    reserve_pct: float
    time_to_pnr_s: float | None
    return_time_s: float | None
    limiting_consumable: Literal["oxygen", "battery", "water", "time", "dose"]


class _WsBase(Model):
    utc: datetime
    sol: int
    lmst: str


class WsTelemetry(_WsBase):
    type: Literal["telemetry"] = "telemetry"
    payload: TelemetryPayload


class WsAlert(_WsBase):
    type: Literal["alert"] = "alert"
    payload: Alert


class WsAlertCleared(_WsBase):
    type: Literal["alert_cleared"] = "alert_cleared"
    payload: AlertClearedPayload


class WsConditions(_WsBase):
    type: Literal["conditions"] = "conditions"
    payload: Conditions


class WsRouteUpdated(_WsBase):
    type: Literal["route_updated"] = "route_updated"
    payload: RouteUpdatedPayload


class WsBudget(_WsBase):
    type: Literal["budget"] = "budget"
    payload: BudgetPayload


WsMessage = Annotated[
    WsTelemetry | WsAlert | WsAlertCleared | WsConditions | WsRouteUpdated | WsBudget,
    Field(discriminator="type"),
]


class WsEnvelope(Model):
    """Enveloppe documentaire d'un message WebSocket, exposée dans l'OpenAPI."""

    message: WsMessage


class ErrorBody(Model):
    detail: str
    code: str | None = None
