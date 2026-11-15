"""Export du plan en GeoJSON et carnet de sortie (X1, EF-15).

Le GeoJSON se rouvre dans QGIS : coordonnées ``[lon, lat]`` en degrés planétocentriques est
(Mars 2000, ``crs_note``), une entité par objet, des propriétés plates (nombres et textes)
pour la table attributaire. Il contient :

- l'itinéraire choisi (``kind = route``), avec ses totaux et son retour garanti ;
- chaque tronçon (``kind = segment``) : distance, durée, dénivelé, pente, consommation ;
- chaque cible dans l'ordre de visite (``kind = target``) ;
- l'habitat (``kind = habitat``) et le point de non-retour s'il est connu (``kind = pnr``).

Les plans viennent de la même source que le simulateur (A4), les cibles d'une source de
cibles remplaçable (les exemples versionnés tant que A2 ne les expose pas).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from marswalk_api.deps import load_example
from marswalk_api.services.a4 import A4Service
from marswalk_core.schemas import (
    Feature,
    FeatureCollection,
    LineStringGeometry,
    Logbook,
    LonLat,
    Plan,
    PointGeometry,
    Route,
    Target,
)
from marswalk_core.site_package import load_site

TargetSource = Callable[[str], Mapping[str, Target]]
"""``site_id`` vers les cibles du site, par identifiant."""

DIGITS = 7
"""Décimales des coordonnées : environ 6 mm sur Mars."""


class PlanNotFoundError(LookupError):
    pass


def example_targets(site_id: str) -> dict[str, Target]:
    """Cibles des exemples versionnés (bouchon de A2), pour le site demandé."""
    targets = [Target.model_validate(t) for t in load_example("targets")]
    return {t.id: t for t in targets if t.site_id == site_id}


def _pt(p: LonLat | tuple[float, float]) -> LonLat:
    return LonLat(round(p[0], DIGITS), round(p[1], DIGITS))


def _selected(plan: Plan) -> Route:
    if not plan.routes:
        raise PlanNotFoundError(f"Le plan {plan.id} n'a pas d'itinéraire")
    return next((r for r in plan.routes if r.id == plan.selected_route_id), plan.routes[0])


def plan_feature_collection(plan: Plan, targets: Mapping[str, Target]) -> FeatureCollection:
    route = _selected(plan)
    t, rc = route.totals, route.return_check
    features = [
        Feature(
            id=route.id,
            geometry=LineStringGeometry(coordinates=[_pt(c) for c in route.geometry.coordinates]),
            properties={
                "kind": "route",
                "plan_id": plan.id,
                "site_id": plan.site_id,
                "variant": route.variant.value,
                "selected": route.id == plan.selected_route_id,
                "distance_m": t.distance_m,
                "duration_s": t.duration_s,
                "walk_time_s": t.walk_time_s,
                "work_time_s": t.work_time_s,
                "ascent_m": t.ascent_m,
                "descent_m": t.descent_m,
                "max_slope_deg": t.max_slope_deg,
                "oxygen_kg": t.consumption.oxygen_kg,
                "battery_wh": t.consumption.battery_wh,
                "water_l": t.consumption.water_l,
                "dose_usv": t.consumption.dose_usv,
                "return_status": rc.status.value,
                "reserve_at_return_pct": rc.reserve_at_return_pct,
                "limiting_consumable": rc.limiting_consumable,
                "departure_utc": plan.departure_utc.isoformat() if plan.departure_utc else None,
            },
        )
    ]
    breaks = _segment_lines(route)
    reasons = {e.segment_index: e.reasons for e in route.explanation}
    for seg, line in zip(route.segments, breaks, strict=True):
        features.append(
            Feature(
                id=f"{route.id}-segment-{seg.index}",
                geometry=LineStringGeometry(coordinates=line),
                properties={
                    "kind": "segment",
                    "route_id": route.id,
                    "index": seg.index,
                    "from": seg.from_target_id or "habitat",
                    "to": seg.to_target_id or "habitat",
                    "distance_m": seg.distance_m,
                    "duration_s": seg.duration_s,
                    "work_time_s": seg.work_time_s,
                    "ascent_m": seg.ascent_m,
                    "descent_m": seg.descent_m,
                    "max_slope_deg": seg.max_slope_deg,
                    "oxygen_kg": seg.consumption.oxygen_kg,
                    "dose_usv": seg.consumption.dose_usv,
                    "reasons": " ; ".join(reasons.get(seg.index, [])),
                },
            )
        )
    order = [s.to_target_id for s in route.segments if s.to_target_id] or plan.target_ids
    seg_by_target = {s.to_target_id: s for s in route.segments if s.to_target_id}
    for rank, target_id in enumerate(order, start=1):
        target = targets.get(target_id)
        arrival = seg_by_target.get(target_id)
        position = target.position if target else (arrival.to_point if arrival else None)
        if position is None:
            continue
        work = arrival.work_time_s if arrival else (target.work_time_s if target else None)
        features.append(
            Feature(
                id=target_id,
                geometry=PointGeometry(coordinates=_pt(position)),
                properties={
                    "kind": "target",
                    "order": rank,
                    "name": target.name if target else target_id,
                    "objective": target.objective if target else None,
                    "measurement": target.measurement if target else None,
                    "work_time_s": work,
                    "priority": target.priority if target else None,
                },
            )
        )
    features.append(
        Feature(
            id="habitat",
            geometry=PointGeometry(coordinates=_pt(plan.start)),
            properties={"kind": "habitat", "name": "Habitat"},
        )
    )
    if rc.point_of_no_return is not None:
        features.append(
            Feature(
                id="pnr",
                geometry=PointGeometry(coordinates=_pt(rc.point_of_no_return)),
                properties={
                    "kind": "pnr",
                    "name": "Point de non-retour",
                    "time_s": rc.point_of_no_return_time_s,
                },
            )
        )
    return FeatureCollection(features=features)


def _segment_lines(route: Route) -> list[list[LonLat]]:
    """Géométrie de chaque tronçon, découpée dans le tracé par ses extrémités."""
    coords = [_pt(c) for c in route.geometry.coordinates]
    lines: list[list[LonLat]] = []
    i = 0
    for seg in route.segments:
        end = _pt(seg.to_point)
        start = i
        j = next((k for k in range(start + 1, len(coords)) if coords[k] == end), None)
        if j is None:
            lines.append([_pt(seg.from_point), end])
            continue
        lines.append(coords[start : j + 1])
        i = j
    return lines


def plan_geojson(
    plan_id: str, plans: Callable[[str], Plan | None], targets: TargetSource
) -> FeatureCollection:
    plan = plans(plan_id)
    if plan is None:
        raise PlanNotFoundError(f"Plan inconnu : {plan_id}")
    load_site(plan.site_id)  # le site doit exister pour que l'export soit relisible
    return plan_feature_collection(plan, targets(plan.site_id))


def logbook(sim: A4Service, eva_id: str) -> Logbook:
    """Carnet de la sortie (tenu par A4), avec le lien de la photo de chaque observation."""
    book = sim.logbook(eva_id)
    photos: dict[str, str] = {
        o.id: o.photo_url for o in sim.observations(eva_id) if o.photo_url is not None
    }
    entries = [
        e.model_copy(update={"text": f"{e.text} (photo : {photos[e.ref_id]})"})
        if e.kind == "observation" and e.ref_id in photos
        else e
        for e in book.entries
    ]
    return book.model_copy(update={"entries": entries})
