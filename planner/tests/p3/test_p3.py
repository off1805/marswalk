"""Tests de la tâche P3 : modèle de marche, budgets et retour garanti.

Critères d'acceptation :
- walking_speed : maximum autour de 0 à −5° de descente, décroissant au-delà.
- return_field : calcul en moins de 2 s, forme identique à la grille.
- return_check : plan trop long → ReturnStatus.fail + cible à couper nommée.
- estimate_route : profil cohérent (distance, temps positifs).
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from marswalk_core.config import load_safety_settings, load_suit
from marswalk_core.grids import RouteOptions
from marswalk_core.paths import repo_root
from marswalk_core.schemas import LonLat, ReturnStatus, SuitModel, Target
from marswalk_core.site_package import load_site
from marswalk_planner.budget import return_check
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.return_field import return_field, return_time_at
from marswalk_planner.variants import plan_variants
from marswalk_planner.walk import walking_speed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suit() -> SuitModel:
    return load_suit()


def _targets() -> list[Target]:
    data = json.loads((repo_root() / "contracts/examples/targets.json").read_text())
    return [Target.model_validate(t) for t in data]


# ---------------------------------------------------------------------------
# walking_speed
# ---------------------------------------------------------------------------


class TestWalkingSpeed:
    def test_maximum_at_slight_downslope(self) -> None:
        """La vitesse est maximale entre 0° et −5° de descente (descente légère)."""
        suit = _suit()
        v0 = walking_speed(0.0, 0, suit)
        v_down2 = walking_speed(-2.0, 0, suit)
        v_down5 = walking_speed(-5.0, 0, suit)
        # La vitesse doit être légèrement supérieure à 0° à une légère descente
        assert v_down2 >= v0 or v_down5 >= v0, (
            f"Attendu v(-2°) ou v(-5°) ≥ v(0°) = {v0:.3f} m/s ; "
            f"obtenu v(-2°)={v_down2:.3f}, v(-5°)={v_down5:.3f}"
        )

    def test_decreasing_steep_upslope(self) -> None:
        """La vitesse décroît pour les fortes montées."""
        suit = _suit()
        v5 = walking_speed(5.0, 0, suit)
        v15 = walking_speed(15.0, 0, suit)
        v25 = walking_speed(25.0, 0, suit)
        assert v5 > v15 > v25, (
            f"Attendu v(5°) > v(15°) > v(25°) ; obtenu {v5:.3f}, {v15:.3f}, {v25:.3f}"
        )

    def test_decreasing_steep_downslope(self) -> None:
        """La vitesse décroît aussi pour les fortes descentes."""
        suit = _suit()
        v5 = walking_speed(-5.0, 0, suit)
        v20 = walking_speed(-20.0, 0, suit)
        v35 = walking_speed(-35.0, 0, suit)
        assert v5 > v20 > v35, (
            f"Attendu v(-5°) > v(-20°) > v(-35°) ; obtenu {v5:.3f}, {v20:.3f}, {v35:.3f}"
        )

    def test_base_speed_at_zero_rock(self) -> None:
        """À pente nulle sur roche, la vitesse vaut base_speed_mps."""
        suit = _suit()
        v = walking_speed(0.0, 0, suit)
        assert abs(v - suit.base_speed_mps) < 1e-6, (
            f"Attendu {suit.base_speed_mps} m/s, obtenu {v:.6f}"
        )

    def test_soil_factor_applied(self) -> None:
        """Les dunes (classe 3) sont plus lentes que la roche (classe 0)."""
        suit = _suit()
        v_rock = walking_speed(0.0, 0, suit)
        v_dune = walking_speed(0.0, 3, suit)
        assert v_dune < v_rock

    def test_clamped_to_max_speed(self) -> None:
        """La vitesse ne dépasse jamais max_speed_mps."""
        suit = _suit()
        for slope in [-10.0, -5.0, -2.0, 0.0, 5.0, 20.0]:
            v = walking_speed(slope, 0, suit)
            assert v <= suit.max_speed_mps + 1e-9, f"v({slope}°) = {v:.3f} > max"

    def test_minimum_speed(self) -> None:
        """La vitesse ne tombe jamais en dessous de 0.1 m/s (même à 45°)."""
        suit = _suit()
        v = walking_speed(45.0, 3, suit)
        assert v >= 0.1

    def test_soil_class_out_of_range_clamped(self) -> None:
        """Les classes de sol hors plage ne plantent pas."""
        suit = _suit()
        v_neg = walking_speed(0.0, -1, suit)
        v_high = walking_speed(0.0, 99, suit)
        assert v_neg > 0
        assert v_high > 0


# ---------------------------------------------------------------------------
# return_field
# ---------------------------------------------------------------------------


class TestReturnField:
    def test_shape_matches_grid(self) -> None:
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        suit = _suit()
        habitat = LonLat(*site.manifest.habitat)
        rf = return_field(grid, habitat, suit)
        assert rf.seconds.shape == site.shape

    def test_habitat_has_zero_return_time(self) -> None:
        """Le temps de retour depuis l'habitat est 0."""
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        suit = _suit()
        habitat = LonLat(*site.manifest.habitat)
        rf = return_field(grid, habitat, suit)
        t = return_time_at(rf, habitat.lon, habitat.lat)
        assert t is not None
        assert abs(t) < 1.0, f"Temps de retour depuis l'habitat = {t}, attendu ≈ 0"

    def test_time_increases_with_distance(self) -> None:
        """Le temps de retour croît avec la distance à l'habitat (sur roche plate)."""
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        suit = _suit()
        habitat = LonLat(*site.manifest.habitat)
        rf = return_field(grid, habitat, suit)
        t_hab = return_time_at(rf, habitat.lon, habitat.lat) or 0.0
        # Rover est plus éloigné de l'habitat
        rover = site.manifest.rover
        if rover is not None:
            t_rover = return_time_at(rf, rover.lon, rover.lat)
            if t_rover is not None:
                assert t_rover > t_hab

    def test_completes_in_under_2s(self) -> None:
        """Le champ de retour se calcule en moins de 2 s sur le site fictif."""
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        suit = _suit()
        habitat = LonLat(*site.manifest.habitat)
        t0 = time.perf_counter()
        return_field(grid, habitat, suit)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"return_field a pris {elapsed:.2f} s (> 2 s)"

    def test_finite_values_in_accessible_area(self) -> None:
        """La majorité de la grille est accessible (valeurs finies)."""
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        suit = _suit()
        habitat = LonLat(*site.manifest.habitat)
        rf = return_field(grid, habitat, suit)
        import numpy as np

        finite_ratio = float(np.isfinite(rf.seconds).mean())
        assert finite_ratio > 0.5, f"Seulement {100 * finite_ratio:.0f} % de cases accessibles"


# ---------------------------------------------------------------------------
# return_check
# ---------------------------------------------------------------------------


class TestReturnCheck:
    def test_ok_for_short_plan(self) -> None:
        """Un plan court sur le site fictif passe la vérification."""
        site = load_site("fictif")
        targets = _targets()[:1]  # une seule cible proche
        routes = plan_variants(
            site, load_safety_settings(), LonLat(*site.manifest.habitat), targets, RouteOptions()
        )
        # Au moins une variante est OK ou marginal
        statuses = {r.return_check.status for r in routes}
        assert ReturnStatus.ok in statuses or ReturnStatus.marginal in statuses, (
            f"Toutes les variantes sont en échec : {statuses}"
        )

    def test_fail_for_impossible_plan(self) -> None:
        """Un plan très long (consommables dépassés) doit être refusé."""

        from marswalk_core.grids import RouteEstimate, SegmentEstimate

        suit = _suit()
        # On simule un trajet qui consomme 200 % de l'oxygène
        seg = SegmentEstimate(
            distance_m=50000.0,
            walk_time_s=50000.0,
            work_time_s=0.0,
            ascent_m=0.0,
            descent_m=0.0,
            max_slope_deg=0.0,
            oxygen_kg=suit.oxygen_capacity_kg * 2.0,  # 200 %
            battery_wh=0.0,
            water_l=0.0,
            dose_usv=0.0,
        )
        est = RouteEstimate(
            segments=[seg],
            samples_distance_m=[0.0, 50000.0],
            samples_position=[LonLat(77.578, 18.381), LonLat(77.580, 18.385)],
            samples_elevation_m=[None, None],
            samples_slope_deg=[None, None],
            samples_time_s=[0.0, 50000.0],
            samples_segment=[0, 0],
        )
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        rf = return_field(grid, LonLat(*site.manifest.habitat), suit)
        rc = return_check(est, rf, suit)
        assert rc.status == ReturnStatus.fail
        assert rc.reserve_at_return_pct < 30.0

    def test_targets_to_cut_named_on_fail(self) -> None:
        """En cas d'échec, la liste targets_to_cut est non vide."""
        from marswalk_core.grids import RouteEstimate, SegmentEstimate

        suit = _suit()
        seg = SegmentEstimate(
            distance_m=50000.0,
            walk_time_s=50000.0,
            work_time_s=0.0,
            ascent_m=0.0,
            descent_m=0.0,
            max_slope_deg=0.0,
            oxygen_kg=suit.oxygen_capacity_kg * 2.5,
            battery_wh=0.0,
            water_l=0.0,
            dose_usv=0.0,
        )
        est = RouteEstimate(
            segments=[seg],
            samples_distance_m=[0.0, 50000.0],
            samples_position=[LonLat(77.578, 18.381), LonLat(77.580, 18.385)],
            samples_elevation_m=[None, None],
            samples_slope_deg=[None, None],
            samples_time_s=[0.0, 50000.0],
            samples_segment=[0, 0],
        )
        site = load_site("fictif")
        grid = build_cost_grid(site, load_safety_settings(), None)
        rf = return_field(grid, LonLat(*site.manifest.habitat), suit)
        rc = return_check(est, rf, suit)
        assert rc.status == ReturnStatus.fail
        assert len(rc.targets_to_cut) > 0, "Aucune cible à couper proposée en cas d'échec"

    def test_limiting_consumable_field(self) -> None:
        """Le champ limiting_consumable est l'un des quatre consommables valides."""
        site = load_site("fictif")
        targets = _targets()[:2]
        routes = plan_variants(
            site, load_safety_settings(), LonLat(*site.manifest.habitat), targets, RouteOptions()
        )
        valid = {"oxygen", "battery", "water", "time", "dose"}
        for r in routes:
            assert r.return_check.limiting_consumable in valid


# ---------------------------------------------------------------------------
# estimate_route (intégration)
# ---------------------------------------------------------------------------


class TestEstimateRoute:
    def test_profile_distance_monotone(self) -> None:
        """La distance cumulée du profil est strictement croissante."""
        site = load_site("fictif")
        targets = _targets()[:2]
        routes = plan_variants(
            site, load_safety_settings(), LonLat(*site.manifest.habitat), targets, RouteOptions()
        )
        for r in routes:
            dists = [s.distance_m for s in r.profile]
            for i in range(1, len(dists)):
                assert dists[i] >= dists[i - 1] - 1e-3, (
                    f"Distance non monotone à l'échantillon {i}: "
                    f"{dists[i - 1]:.2f} → {dists[i]:.2f}"
                )

    def test_totals_consistent(self) -> None:
        """Les totaux de la route correspondent à la somme des segments."""
        site = load_site("fictif")
        targets = _targets()[:2]
        routes = plan_variants(
            site, load_safety_settings(), LonLat(*site.manifest.habitat), targets, RouteOptions()
        )
        for r in routes:
            seg_sum_d = sum(s.distance_m for s in r.segments)
            seg_sum_t = sum(s.duration_s + s.work_time_s for s in r.segments)
            assert abs(r.totals.distance_m - seg_sum_d) < 1.0, (
                f"Distance totale {r.totals.distance_m:.1f} ≠ somme segments {seg_sum_d:.1f}"
            )
            assert abs(r.totals.duration_s - seg_sum_t) < 1.0, (
                f"Durée totale {r.totals.duration_s:.1f} ≠ somme segments {seg_sum_t:.1f}"
            )

    def test_consumption_positive(self) -> None:
        """Les consommations sont toutes positives."""
        site = load_site("fictif")
        targets = _targets()[:2]
        routes = plan_variants(
            site, load_safety_settings(), LonLat(*site.manifest.habitat), targets, RouteOptions()
        )
        for r in routes:
            assert r.totals.consumption.oxygen_kg > 0
            assert r.totals.consumption.battery_wh > 0
            assert r.totals.consumption.dose_usv > 0

    def test_speed_varies_with_slope(self) -> None:
        """Les segments sur pente forte durent plus longtemps que sur terrain plat
        pour la même distance, ce qui montre que la vitesse varie."""
        suit = _suit()
        v_flat = walking_speed(0.0, 0, suit)
        v_steep = walking_speed(20.0, 0, suit)
        # Sur terrain à 20°, la vitesse doit être inférieure à terrain plat
        assert v_steep < v_flat

    def test_plan_too_long_refused_with_target(self) -> None:
        """Un plan trop long sur le site fictif est refusé avec la cible à couper."""
        # Créer une combinaison avec très peu d'oxygène pour forcer l'échec
        small_suit = SuitModel(
            name="test-small",
            oxygen_capacity_kg=0.001,  # 1 g : insuffisant pour toute sortie
            oxygen_rate_kg_h=0.08,
            battery_capacity_wh=1500.0,
            battery_rate_w=150.0,
            water_capacity_l=4.0,
            water_rate_l_h=0.3,
        )
        site = load_site("fictif")
        targets = _targets()[:3]
        opts = RouteOptions(suit=small_suit)
        routes = plan_variants(
            site,
            load_safety_settings(),
            LonLat(*site.manifest.habitat),
            targets,
            opts,
        )
        # Au moins une route doit être en échec avec targets_to_cut
        failed = [r for r in routes if r.return_check.status == ReturnStatus.fail]
        assert len(failed) > 0, "Aucune route en échec avec oxygène minimal"
        for r in failed:
            assert len(r.return_check.targets_to_cut) > 0, (
                "Plan en échec mais aucune cible à couper proposée"
            )


# ---------------------------------------------------------------------------
# Hypothèses sourcées
# ---------------------------------------------------------------------------


def test_hypotheses_marche_exists() -> None:
    """Le fichier d'hypothèses de marche existe et est non vide."""
    path = repo_root() / "docs" / "science" / "hypotheses-marche.md"
    assert path.exists(), f"Fichier manquant : {path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 500, "Fichier hypotheses-marche.md trop court"
    # Vérifier que les sources clés sont mentionnées
    assert "Tobler" in content
    assert "Waligora" in content
    assert "Apollo" in content


def test_return_field_on_coarse_grid_keeps_shape_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Grande grille (Jezero) : champ calculé sur une maille agrégée, même forme en sortie."""
    import marswalk_planner.return_field as rf_mod

    site = load_site("fictif")
    grid = build_cost_grid(site, load_safety_settings(), None)
    habitat = LonLat(*site.manifest.habitat)
    fine = return_field(grid, habitat, _suit())
    monkeypatch.setattr(rf_mod, "MAX_FIELD_CELLS", grid.cost.size // 9)
    coarse = return_field(grid, habitat, _suit())
    assert coarse.seconds.shape == fine.seconds.shape
    t0 = return_time_at(coarse, habitat.lon, habitat.lat)
    assert t0 is not None and t0 < 10.0
    both = np.isfinite(fine.seconds) & np.isfinite(coarse.seconds) & (fine.seconds > 300)
    ratio = coarse.seconds[both] / fine.seconds[both]
    assert 0.7 < float(np.median(ratio)) < 1.3
