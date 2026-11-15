"""Tests d'intégration D2 : run_derive sur le site fictif."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import rasterio

from marswalk_core.paths import repo_root
from marswalk_pipeline.derived import run_derive

FICTIF_PACKAGE = repo_root() / "fixtures" / "sites" / "fictif"
FICTIF_COG = FICTIF_PACKAGE / "cog"
EXPECTED_LAYERS = [
    "slope",
    "roughness",
    "hillshade",
    "obstacles",
    "scarps",
    "loose_soil",
    "radio_coverage",
    "illumination",
]


def _has_fictif_dem() -> bool:
    return (FICTIF_COG / "dem.tif").exists()


@pytest.fixture(scope="module")
def fictif_derived_dir(tmp_path_factory):
    """Exécute run_derive une seule fois et retourne le répertoire de sortie."""
    if not _has_fictif_dem():
        pytest.skip("DEM fictif absent")
    derived_dir = tmp_path_factory.mktemp("fictif_derived")
    results = run_derive(
        "fictif",
        aligned_dir=FICTIF_COG,
        derived_dir=derived_dir,
    )
    return derived_dir, results


class TestDeriveOnFictifSite:
    def test_derive_on_fictif_site(self, fictif_derived_dir):
        """run_derive('fictif') produit les 8 couches."""
        derived_dir, results = fictif_derived_dir

        for layer in EXPECTED_LAYERS:
            assert layer in results, f"Couche {layer} absente du résultat"
            path = derived_dir / f"{layer}.tif"
            assert path.exists(), f"Fichier {layer}.tif non produit"

    def test_no_error_in_results(self, fictif_derived_dir):
        """Aucun statut d'erreur dans les résultats."""
        _, results = fictif_derived_dir
        errors = {k: v for k, v in results.items() if v.startswith("error")}
        assert len(errors) == 0, f"Erreurs : {errors}"


class TestDerivedFilesHaveCorrectGrid:
    def test_derived_files_have_correct_grid(self, fictif_derived_dir):
        """Toutes les sorties ont exactement la même grille que dem.tif."""
        derived_dir, _results = fictif_derived_dir

        with rasterio.open(FICTIF_COG / "dem.tif") as ref_ds:
            ref_w = ref_ds.width
            ref_h = ref_ds.height
            ref_tf = ref_ds.transform

        for layer in EXPECTED_LAYERS:
            path = derived_dir / f"{layer}.tif"
            if not path.exists():
                continue
            with rasterio.open(path) as ds:
                assert ds.width == ref_w, f"{layer}: width {ds.width} ≠ {ref_w}"
                assert ds.height == ref_h, f"{layer}: height {ds.height} ≠ {ref_h}"
                assert abs(ds.transform.a - ref_tf.a) < 1e-3, (
                    f"{layer}: résolution {ds.transform.a} ≠ {ref_tf.a}"
                )
                assert abs(ds.transform.c - ref_tf.c) < 1.0, (
                    f"{layer}: origin x {ds.transform.c} ≠ {ref_tf.c}"
                )

    def test_derived_files_are_float32(self, fictif_derived_dir):
        """Toutes les sorties sont en float32."""
        derived_dir, _results = fictif_derived_dir
        for layer in EXPECTED_LAYERS:
            path = derived_dir / f"{layer}.tif"
            if not path.exists():
                continue
            with rasterio.open(path) as ds:
                assert ds.dtypes[0] == "float32", f"{layer}: dtype {ds.dtypes[0]} ≠ float32"

    def test_derived_files_have_nodata(self, fictif_derived_dir):
        """Toutes les sorties ont nodata=-9999."""
        derived_dir, _results = fictif_derived_dir
        for layer in EXPECTED_LAYERS:
            path = derived_dir / f"{layer}.tif"
            if not path.exists():
                continue
            with rasterio.open(path) as ds:
                assert ds.nodata is not None, f"{layer}: nodata non défini"
                assert abs(float(ds.nodata) - (-9999.0)) < 1.0, (
                    f"{layer}: nodata {ds.nodata} ≠ -9999"
                )


class TestSlope15DegAccuracy:
    def test_slope_15deg_accuracy_on_tilted_dem(self):
        """Critère d'acceptation : plan incliné 15° → pente à 0.1° près."""
        from marswalk_pipeline.derived.slope import compute_slope

        size = 200
        resolution_m = 2.0
        slope_deg = 15.0
        slope_m_per_m = np.tan(np.radians(slope_deg))
        cols = np.arange(size, dtype=np.float32)
        # Tableau 200×200 avec pente vers l'est
        dem = (
            np.broadcast_to(-2500.0 + cols * slope_m_per_m * resolution_m, (size, size))
            .copy()
            .astype(np.float32)
        )

        slope = compute_slope(dem, resolution_m=resolution_m, nodata=-9999.0)
        interior = slope[2:-2, 2:-2]
        valid = interior != -9999.0
        assert valid.any()
        mean_slope = float(np.mean(interior[valid]))
        assert abs(mean_slope - 15.0) < 0.1, (
            f"Pente attendue 15.0°, obtenu {mean_slope:.4f}° (tolérance 0.1°)"
        )


class TestTotalRuntime:
    def test_total_runtime(self):
        """Le calcul complet sur le site fictif tient en moins de 5 minutes."""
        if not _has_fictif_dem():
            pytest.skip("DEM fictif absent")

        with tempfile.TemporaryDirectory() as tmpdir:
            t0 = time.monotonic()
            results = run_derive(
                "fictif",
                aligned_dir=FICTIF_COG,
                derived_dir=Path(tmpdir),
            )
            elapsed = time.monotonic() - t0

        n_ok = sum(1 for s in results.values() if s == "ok")
        print(f"\n[D2] {n_ok} couches en {elapsed:.1f}s")
        assert elapsed < 300.0, f"Calcul trop lent : {elapsed:.1f}s > 300s"
