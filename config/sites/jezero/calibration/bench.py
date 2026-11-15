"""Mesures de calibration I1 sur le vrai paquet de Jezero (ENF-02).

    uv run python config/sites/jezero/calibration/bench.py [--site jezero] [--preset standard]

Lit le paquet installé (data/packages/<site>/), les cibles de targets-seed.geojson et le
préréglage de config/safety.yaml, puis chronomètre la grille de coût, les zones dangereuses,
le champ de retour, un plan à trois variantes sur toutes les cibles et le recalcul après
le déplacement d'une cible. Affiche aussi la part de l'emprise interdite et un résumé des
variantes, pour juger si les seuils donnent des itinéraires crédibles.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from marswalk_core.config import load_safety_settings, load_suit
from marswalk_core.grids import RouteOptions
from marswalk_core.paths import config_dir
from marswalk_core.schemas import LonLat, Target
from marswalk_core.site_package import load_site
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks, hazard_polygons
from marswalk_planner.return_field import return_field
from marswalk_planner.variants import plan_variants


def _targets(site_id: str) -> list[Target]:
    path = config_dir() / "sites" / site_id / "targets-seed.geojson"
    now = datetime.now(UTC)
    out = []
    for f in json.loads(Path(path).read_text(encoding="utf-8"))["features"]:
        p = f["properties"]
        out.append(
            Target(
                id=f["id"],
                site_id=site_id,
                created_at=now,
                updated_at=now,
                name=p["name"],
                kind=p.get("kind", "science"),
                position=LonLat(*f["geometry"]["coordinates"][:2]),
                work_time_s=p.get("work_time_s", 900.0),
                priority=p.get("priority", 2),
            )
        )
    return out


def _clock(label: str, fn, budget_s: float | None = None):  # type: ignore[no-untyped-def]
    t0 = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t0
    verdict = (
        "" if budget_s is None else ("  OK" if dt < budget_s else f"  TROP LENT (< {budget_s} s)")
    )
    print(f"{label:<42} {dt:7.2f} s{verdict}")
    return result, dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="jezero")
    ap.add_argument("--preset", default=None)
    args = ap.parse_args()

    site = load_site(args.site)
    settings = load_safety_settings(args.preset)
    suit = load_suit()
    targets = _targets(args.site)
    habitat = LonLat(*site.manifest.habitat)
    print(f"Site {args.site}, préréglage {settings.preset}, {len(targets)} cibles\n")

    masks, _ = _clock("Masques de danger", lambda: hazard_masks(site, settings))
    forbidden = np.asarray(masks.forbidden)
    print(f"  part interdite de l'emprise : {100 * forbidden.mean():.1f} %")
    _clock("Polygones des zones (GET /hazards)", lambda: hazard_polygons(site, settings))
    grid, _ = _clock(
        "Grille de coût 2 m (P1, < 1 s)", lambda: build_cost_grid(site, settings, None), 1.0
    )
    _clock("Champ de retour (P3, < 2 s)", lambda: return_field(grid, habitat, suit), 2.0)

    options = RouteOptions(return_to=habitat, optimize_order=True, suit=suit)
    routes, _ = _clock(
        f"Plan 3 variantes, {len(targets)} cibles (< 5 s)",
        lambda: plan_variants(site, settings, habitat, targets, options),
        5.0,
    )
    moved = [
        t.model_copy(update={"position": LonLat(t.position.lon + 0.0005, t.position.lat)})
        if i == 0
        else t
        for i, t in enumerate(targets)
    ]
    _clock(
        "Recalcul après déplacement d'une cible (< 2 s)",
        lambda: plan_variants(site, settings, habitat, moved, options),
        2.0,
    )

    print("\nVariantes :")
    for r in routes:
        t = r.totals
        rc = r.return_check
        print(
            f"  {r.variant.value:<8} {t.distance_m / 1000:5.2f} km  {t.duration_s / 3600:4.1f} h  "
            f"pente max {t.max_slope_deg:4.1f}°  "
            f"retour {rc.status.value} ({rc.reserve_at_return_pct:.0f} %)  "
            f"ordre {[s.to_target_id or 'habitat' for s in r.segments]}"
        )
        for s in r.segments:
            print(
                f"      tronçon {s.index} {s.from_target_id or 'habitat'} -> "
                f"{s.to_target_id or 'habitat'} : {s.distance_m:6.0f} m, "
                f"travail {s.work_time_s:5.0f} s"
            )
        for w in r.warnings:
            print(f"      ! {w}")


if __name__ == "__main__":
    main()
