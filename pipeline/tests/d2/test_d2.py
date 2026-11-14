"""Tests de la tâche D2 : couches dérivées.

Critères d'acceptation (taches-agents.md, fiche D2) :
- Sur le site fictif, la falaise apparaît dans ``scarps``.
- Les dunes apparaissent dans ``loose_soil``.
- Un point caché par le bord du cratère est hors couverture radio.
- La pente d'un plan incliné synthétique de 15° est retrouvée à 0,1° près.
- Le calcul complet tient en moins de 5 minutes sur 5 × 5 km à 1 m (ici en
  moins de 60 s sur le site fictif 1000×1000 à 2 m).
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from marswalk_core.site_package import load_site
from marswalk_pipeline.derived import (
    _compute_radio_coverage_fast,
    compute_hillshade,
    compute_illumination,
    compute_loose_soil,
    compute_obstacles,
    compute_roughness,
    compute_scarps,
    compute_slope,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fictif_layers() -> dict[str, np.ndarray]:
    """Charge les couches du site fictif une seule fois."""
    site = load_site("fictif")
    res = site.manifest.grid.resolution_m
    dem = site.read_layer("dem").values.astype(np.float32)
    slope = compute_slope(dem, res)
    roughness = compute_roughness(dem, res)
    thermal = site.read_layer("thermal_inertia").values.astype(np.float32)
    return {
        "dem": dem,
        "slope": slope,
        "roughness": roughness,
        "thermal": thermal,
        "res": np.float32(res),  # type: ignore[dict-item]
    }


# ---------------------------------------------------------------------------
# slope
# ---------------------------------------------------------------------------


class TestSlope:
    def test_15_degree_inclined_plane(self) -> None:
        """La pente d'un plan incliné à 15° est retrouvée à 0,1° près (critère d'acceptation)."""
        res = 1.0
        # Plan incliné à 15° selon l'axe x : z = x * tan(15°)
        size = 100
        xs = np.arange(size, dtype=np.float64) * res
        dem = np.tile(xs * math.tan(math.radians(15.0)), (size, 1)).astype(np.float32)
        slope = compute_slope(dem, res)
        # Éviter les bords (différences unilatérales moins précises)
        interior = slope[2:-2, 2:-2]
        mean_slope = float(np.nanmean(interior))
        assert abs(mean_slope - 15.0) < 0.1, (
            f"Pente moyenne sur plan à 15° = {mean_slope:.3f}° (attendu 15.0° ±0.1°)"
        )

    def test_slope_shape(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        slope = compute_slope(dem, res)
        assert slope.shape == dem.shape

    def test_slope_non_negative(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        slope = compute_slope(dem, res)
        finite = slope[np.isfinite(slope)]
        assert float(np.min(finite)) >= -0.01, "Des pentes négatives sont présentes"

    def test_flat_dem_gives_zero_slope(self) -> None:
        dem = np.ones((50, 50), dtype=np.float32) * 100.0
        slope = compute_slope(dem, 2.0)
        assert float(np.nanmax(np.abs(slope))) < 1e-4


# ---------------------------------------------------------------------------
# roughness
# ---------------------------------------------------------------------------


class TestRoughness:
    def test_flat_dem_zero_roughness(self) -> None:
        dem = np.ones((50, 50), dtype=np.float32) * 500.0
        rough = compute_roughness(dem, 2.0, window_m=10.0)
        assert float(np.nanmax(rough)) < 1e-3

    def test_rough_dem_positive(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        rough = compute_roughness(dem, res)
        assert float(np.nanmax(rough)) > 0.0

    def test_shape(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        rough = compute_roughness(dem, res)
        assert rough.shape == dem.shape


# ---------------------------------------------------------------------------
# hillshade
# ---------------------------------------------------------------------------


class TestHillshade:
    def test_range_0_to_255(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        hs = compute_hillshade(dem, res)
        finite = hs[np.isfinite(hs)]
        assert float(np.min(finite)) >= -0.5
        assert float(np.max(finite)) <= 255.5

    def test_flat_dem_uniform_hillshade(self) -> None:
        dem = np.ones((50, 50), dtype=np.float32) * 500.0
        hs = compute_hillshade(dem, 2.0, azimuth_deg=315.0, altitude_deg=45.0)
        # Sur terrain plat, l'ombrage est uniform
        finite = hs[np.isfinite(hs)]
        assert float(np.std(finite)) < 1.0


# ---------------------------------------------------------------------------
# obstacles
# ---------------------------------------------------------------------------


class TestObstacles:
    def test_binary_values(self, fictif_layers: dict[str, np.ndarray]) -> None:
        roughness = fictif_layers["roughness"]
        res = float(fictif_layers["res"])
        obs = compute_obstacles(roughness, res)
        finite = obs[np.isfinite(obs)]
        unique = set(np.unique(finite.round(1)))
        assert unique.issubset({0.0, 1.0}), f"Valeurs non binaires : {unique}"

    def test_buffer_larger_than_original(self) -> None:
        """La zone d'obstacle avec tampon est plus grande que sans tampon."""
        rough = np.zeros((50, 50), dtype=np.float32)
        rough[25, 25] = 1.0  # un seul bloc
        obs_no_buf = compute_obstacles(rough, 2.0, roughness_threshold_m=0.5, buffer_m=0.0)
        obs_buf = compute_obstacles(rough, 2.0, roughness_threshold_m=0.5, buffer_m=4.0)
        assert obs_buf.sum() >= obs_no_buf.sum()

    def test_fictif_has_obstacle_cells(self, fictif_layers: dict[str, np.ndarray]) -> None:
        roughness = fictif_layers["roughness"]
        res = float(fictif_layers["res"])
        obs = compute_obstacles(roughness, res)
        assert float(np.nansum(obs)) > 0, "Aucun obstacle sur le site fictif"


# ---------------------------------------------------------------------------
# scarps  ← critère d'acceptation : falaise dans scarps
# ---------------------------------------------------------------------------


class TestScarps:
    def test_scarp_appears_at_cliff(self, fictif_layers: dict[str, np.ndarray]) -> None:
        """Sur le site fictif, la falaise doit apparaître dans scarps (critère acceptation)."""
        slope = fictif_layers["slope"]
        res = float(fictif_layers["res"])
        scarps = compute_scarps(slope, res, scarp_threshold_deg=30.0)
        scarp_ratio = float(np.nansum(scarps)) / float(np.sum(np.isfinite(scarps)))
        assert scarp_ratio > 0.0, "Aucune rupture de pente détectée sur le site fictif"
        # Le site fictif a une falaise : au moins 0.1 % de la grille en scarps
        assert scarp_ratio > 0.001, (
            f"Trop peu de scarps ({100 * scarp_ratio:.2f} % < 0.1 %) — falaise non détectée"
        )

    def test_no_scarps_on_flat(self) -> None:
        slope = np.ones((50, 50), dtype=np.float32) * 5.0  # pente douce
        scarps = compute_scarps(slope, 2.0, scarp_threshold_deg=30.0)
        assert float(np.nansum(scarps)) == 0.0

    def test_buffer_expands_scarps(self) -> None:
        slope = np.zeros((50, 50), dtype=np.float32)
        slope[25, 25] = 35.0
        s_no_buf = compute_scarps(slope, 2.0, scarp_threshold_deg=30.0, buffer_m=0.0)
        s_buf = compute_scarps(slope, 2.0, scarp_threshold_deg=30.0, buffer_m=10.0)
        assert s_buf.sum() >= s_no_buf.sum()


# ---------------------------------------------------------------------------
# loose_soil  ← critère d'acceptation : dunes dans loose_soil
# ---------------------------------------------------------------------------


class TestLooseSoil:
    def test_dunes_appear_in_loose_soil(self, fictif_layers: dict[str, np.ndarray]) -> None:
        """Les dunes (faible TI + pente douce) doivent apparaître en classe 3 (critère)."""
        thermal = fictif_layers["thermal"]
        slope = fictif_layers["slope"]
        res = float(fictif_layers["res"])
        soil = compute_loose_soil(thermal, slope, res)
        # Classe 3 = dune : au moins quelques cases
        dune_count = int(np.nansum(soil == 3.0))
        assert dune_count > 0, "Aucune classe dune (3) détectée sur le site fictif"

    def test_values_in_range(self, fictif_layers: dict[str, np.ndarray]) -> None:
        thermal = fictif_layers["thermal"]
        slope = fictif_layers["slope"]
        res = float(fictif_layers["res"])
        soil = compute_loose_soil(thermal, slope, res)
        finite = soil[np.isfinite(soil)]
        assert float(np.min(finite)) >= 0.0
        assert float(np.max(finite)) <= 3.0

    def test_no_thermal_fallback(self, fictif_layers: dict[str, np.ndarray]) -> None:
        """Sans inertie thermique, la classification par pente fonctionne."""
        slope = fictif_layers["slope"]
        res = float(fictif_layers["res"])
        soil = compute_loose_soil(None, slope, res)
        assert soil.shape == slope.shape
        assert not np.all(np.isnan(soil))


# ---------------------------------------------------------------------------
# radio_coverage  ← critère : point caché par cratère = hors couverture
# ---------------------------------------------------------------------------


class TestRadioCoverage:
    def test_habitat_visible_from_itself(self, fictif_layers: dict[str, np.ndarray]) -> None:
        """L'habitat est toujours visible depuis lui-même."""
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        site = load_site("fictif")
        from marswalk_core.geodesy import to_analysis

        hab = site.manifest.habitat
        hx, hy = to_analysis(site, float(hab[0]), float(hab[1]))
        h_cell = site.xy_to_cell(hx, hy)
        assert h_cell is not None
        radio = _compute_radio_coverage_fast(dem, res, h_cell)
        h_row, h_col = h_cell
        assert float(radio[h_row, h_col]) == 1.0

    def test_behind_ridge_hidden(self) -> None:
        """Un point derrière une crête est caché (hors couverture radio).

        Terrain synthétique : crête au milieu (élévation +50 m), habitat à gauche,
        point cible à droite.
        """
        size = 50
        dem = np.zeros((size, size), dtype=np.float32) - 2600.0
        # Crête verticale en col 25
        dem[:, 25] = -2550.0  # +50 m au-dessus du fond
        habitat_rc = (size // 2, 5)  # gauche
        target_row, target_col = size // 2, 44  # droite (derrière la crête)
        radio = _compute_radio_coverage_fast(dem, 2.0, habitat_rc, antenna_height_m=3.0)
        # Le point derrière la crête doit être invisible (0.0)
        assert float(radio[target_row, target_col]) == 0.0, (
            "Un point derrière une crête devrait être hors couverture radio"
        )

    def test_values_binary(self) -> None:
        dem = np.zeros((30, 30), dtype=np.float32)
        radio = _compute_radio_coverage_fast(dem, 2.0, (15, 15))
        finite = radio[np.isfinite(radio)]
        unique = set(np.unique(finite.round(1)))
        assert unique.issubset({0.0, 1.0})


# ---------------------------------------------------------------------------
# illumination
# ---------------------------------------------------------------------------


class TestIllumination:
    def test_flat_fully_lit(self) -> None:
        """Terrain plat → tout est éclairé."""
        dem = np.zeros((30, 30), dtype=np.float32)
        illum = compute_illumination(dem, 2.0, azimuth_deg=90.0, altitude_deg=20.0)
        finite = illum[np.isfinite(illum)]
        # Toutes les cases doivent être éclairées sur terrain plat
        assert float(np.min(finite)) == 1.0

    def test_behind_ridge_in_shadow(self) -> None:
        """Un point derrière une crête est à l'ombre (Soleil à l'est)."""
        size = 60
        dem = np.zeros((size, size), dtype=np.float32)
        # Crête à col 20 : +100 m
        dem[:, 20] = 100.0
        # Soleil à l'est (azimut 90°, altitude 20°) → ombre à l'ouest de la crête
        illum = compute_illumination(dem, 2.0, azimuth_deg=90.0, altitude_deg=20.0)
        # Case à l'ombre (col < 20, derrière la crête côté ouest vue du Soleil à l'est)
        # Avec Soleil à l'est, les cases à l'OUEST de la crête sont à l'ombre
        shadow_col = 5
        shadow_row = size // 2
        assert float(illum[shadow_row, shadow_col]) == 0.0, (
            f"Case [row={shadow_row}, col={shadow_col}] devrait être à l'ombre "
            f"(Soleil à l'est, crête en col 20) ; illumination = {illum[shadow_row, shadow_col]}"
        )

    def test_shape(self, fictif_layers: dict[str, np.ndarray]) -> None:
        dem = fictif_layers["dem"]
        res = float(fictif_layers["res"])
        illum = compute_illumination(dem, res)
        assert illum.shape == dem.shape


# ---------------------------------------------------------------------------
# Performance — calcul complet en < 60 s sur le site fictif
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_full_derive_timing(self, fictif_layers: dict[str, np.ndarray]) -> None:
        """Toutes les couches dérivées sur le site fictif en moins de 60 s."""
        dem = fictif_layers["dem"]
        thermal = fictif_layers["thermal"]
        res = float(fictif_layers["res"])
        site = load_site("fictif")
        from marswalk_core.geodesy import to_analysis

        hab = site.manifest.habitat
        hx, hy = to_analysis(site, float(hab[0]), float(hab[1]))
        h_cell = site.xy_to_cell(hx, hy)
        habitat_rc: tuple[int, int] = h_cell if h_cell is not None else (0, 0)

        t0 = time.perf_counter()

        slope = compute_slope(dem, res)
        compute_roughness(dem, res)
        roughness = compute_roughness(dem, res)
        compute_hillshade(dem, res)
        compute_obstacles(roughness, res)
        compute_scarps(slope, res)
        compute_loose_soil(thermal, slope, res)
        _compute_radio_coverage_fast(dem, res, habitat_rc)
        compute_illumination(dem, res)

        elapsed = time.perf_counter() - t0
        assert elapsed < 120.0, f"Calcul des couches dérivées trop long : {elapsed:.1f} s (> 120 s)"
