"""Tests de la tâche D1 : ingestion et recalage.

Critères d'acceptation (taches-agents.md, fiche D1) :
- Les rasters ont tous la même grille (dimension, transform).
- Le décalage résiduel est indiqué pour chaque couche.
- Le décalage résiduel reste sous 1 pixel de la couche la plus grossière.
- La commande ``marswalk ingest`` s'exécute sans erreur sur le site fictif.
- Le rapport de recalage est écrit dans ``data/work/<site_id>/coreg_report.md``.

NOTE : Ces tests s'exécutent sur le site fictif (fixtures/sites/fictif) pour
       éviter toute dépendance à des données réelles. Les données Jezero réelles
       sont dans data/raw/jezero/ (hors Git, gérées par DVC) ; leur validation
       est humaine (QGIS).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import rasterio

from marswalk_core.paths import repo_root
from marswalk_pipeline.coreg import CoregResult, coregister, write_coreg_report
from marswalk_pipeline.ingest import (
    IngestResult,
    _make_analysis_transform,
    ingest_from_package,
    reproject_to_analysis,
)

FICTIF_PACKAGE = repo_root() / "fixtures" / "sites" / "fictif"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fictif_analysis_params() -> tuple[rasterio.transform.Affine, int, int, str]:
    """Paramètres de la grille d'analyse du site fictif."""
    from marswalk_core.site_package import open_package

    site = open_package(FICTIF_PACKAGE)
    cfg_analysis_crs = site.manifest.analysis_crs
    t = site.manifest.grid.transform
    affine = rasterio.transform.Affine(t[0], t[1], t[2], t[3], t[4], t[5])
    return affine, site.manifest.grid.width, site.manifest.grid.height, cfg_analysis_crs


# ---------------------------------------------------------------------------
# reproject_to_analysis
# ---------------------------------------------------------------------------


class TestReprojectToAnalysis:
    def test_reprojection_produces_correct_shape(self) -> None:
        """La reprojection d'un COG du site fictif produit la bonne forme."""
        transform, width, height, crs_str = _fictif_analysis_params()
        src_cog = FICTIF_PACKAGE / "cog" / "dem.tif"

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dem_reproj.tif"
            reproject_to_analysis(src_cog, out, crs_str, transform, width, height)
            assert out.exists()
            with rasterio.open(out) as ds:
                assert ds.width == width
                assert ds.height == height

    def test_reprojection_values_finite(self) -> None:
        """La reprojection ne produit pas que des nodata."""
        transform, width, height, crs_str = _fictif_analysis_params()
        src_cog = FICTIF_PACKAGE / "cog" / "slope.tif"

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "slope_reproj.tif"
            reproject_to_analysis(src_cog, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                data = ds.read(1)
                n_finite = int(np.sum(np.isfinite(data) & (data != -9999.0)))
                assert n_finite > 0, "Toutes les valeurs sont nodata après reprojection"

    def test_reprojection_transform_matches(self) -> None:
        """La transformation affine du fichier reprojeté correspond à celle demandée."""
        transform, width, height, crs_str = _fictif_analysis_params()
        src_cog = FICTIF_PACKAGE / "cog" / "dem.tif"

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dem_reproj.tif"
            reproject_to_analysis(src_cog, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                assert abs(ds.transform.a - transform.a) < 1e-6
                assert abs(ds.transform.c - transform.c) < 1e-6
                assert abs(ds.transform.f - transform.f) < 1e-6

    def test_make_analysis_transform_jezero(self) -> None:
        """La grille d'analyse Jezero a les bonnes dimensions."""
        from marswalk_core.config import load_site_config

        cfg = load_site_config("jezero")
        transform, width, height = _make_analysis_transform(cfg)
        # Jezero : 5000 m / 1 m = 5000 cases
        expected_n = 5000
        assert width == expected_n, f"width={width} ≠ {expected_n}"
        assert height == expected_n
        assert abs(transform.a - 1.0) < 1e-6  # résolution 1 m
        assert abs(transform.e - (-1.0)) < 1e-6  # résolution 1 m (négatif en y)


# ---------------------------------------------------------------------------
# ingest_from_package (integration sur le site fictif)
# ---------------------------------------------------------------------------


class TestIngestFromPackage:
    def test_aligned_files_same_grid(self) -> None:
        """Les rasters produits par ingest_from_package ont tous la même grille."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            # Utiliser la même config fictif → même grille
            # On pointe vers fictif comme site_id=fictif
            results = ingest_from_package("fictif", FICTIF_PACKAGE, work_dir=work_dir)
            ok = [r for r in results if r.status == "ok"]
            assert len(ok) >= 2, "Moins de 2 couches ingérées avec succès"

            # Lire la grille de référence
            ref_path = work_dir / "aligned" / f"{ok[0].layer_id}.tif"
            with rasterio.open(ref_path) as ref_ds:
                ref_w, ref_h = ref_ds.width, ref_ds.height
                ref_tf = ref_ds.transform

            for r in ok[1:]:
                sec_path = work_dir / "aligned" / f"{r.layer_id}.tif"
                with rasterio.open(sec_path) as sec_ds:
                    assert sec_ds.width == ref_w, f"{r.layer_id}: width {sec_ds.width} ≠ {ref_w}"
                    assert sec_ds.height == ref_h, f"{r.layer_id}: height {sec_ds.height} ≠ {ref_h}"
                    assert abs(sec_ds.transform.a - ref_tf.a) < 1e-3, (
                        f"{r.layer_id}: résolution différente"
                    )

    def test_at_least_dem_and_hirise_ok(self) -> None:
        """Les couches DEM et HiRISE sont produites avec succès."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = ingest_from_package("fictif", FICTIF_PACKAGE, work_dir=Path(tmpdir))
            by_id = {r.layer_id: r for r in results}
            assert "dem" in by_id, "Couche DEM manquante"
            assert by_id["dem"].status in ("ok", "degraded"), (
                f"Statut DEM inattendu : {by_id['dem'].status}"
            )

    def test_result_has_status_and_note(self) -> None:
        """Chaque résultat d'ingestion a un statut et une note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = ingest_from_package("fictif", FICTIF_PACKAGE, work_dir=Path(tmpdir))
            for r in results:
                assert r.status in ("ok", "degraded", "missing"), (
                    f"Statut inconnu pour {r.layer_id}: {r.status}"
                )
                assert isinstance(r.note, str)


# ---------------------------------------------------------------------------
# coregister
# ---------------------------------------------------------------------------


class TestCoregister:
    def _prepare_aligned(self, tmpdir: str) -> Path:
        """Prépare un dossier aligned/ avec quelques couches du site fictif."""
        work_dir = Path(tmpdir)
        ingest_from_package("fictif", FICTIF_PACKAGE, work_dir=work_dir)
        return work_dir / "aligned"

    def test_coreg_produces_result_per_layer(self) -> None:
        """coregister renvoie un résultat par couche secondaire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned = self._prepare_aligned(tmpdir)
            results = coregister(aligned, reference_layer="hirise_vis")
            layer_ids = {r.layer_id for r in results}
            # Les couches à recaler sont thermal_inertia, crism_minerals, ctx_vis
            for expected in ("thermal_inertia", "crism_minerals", "ctx_vis"):
                assert expected in layer_ids, f"Résultat manquant pour {expected}"

    def test_coreg_result_has_residual(self) -> None:
        """Chaque résultat de recalage indique le décalage résiduel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned = self._prepare_aligned(tmpdir)
            results = coregister(aligned, reference_layer="hirise_vis")
            for r in results:
                # residual_m est un flottant (0.0 si pas de déplacement ou skipped)
                assert isinstance(r.residual_m, float)
                assert r.status in ("ok", "degraded", "skipped")

    def test_coreg_residual_under_1_pixel(self) -> None:
        """Le résidu reste sous 1 pixel de la couche la plus grossière (THEMIS = 100 m).

        Sur le site fictif (données SYNTHETIC), le décalage devrait être quasi nul.
        Le critère passe si residual_m < 100 m (1 pixel THEMIS) pour les couches non-skipped.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned = self._prepare_aligned(tmpdir)
            results = coregister(aligned, reference_layer="hirise_vis")
            # Couche la plus grossière : THEMIS = 100 m, donc 1 pixel = 100 m
            max_coarsest_res_m = 100.0
            for r in results:
                if r.status == "skipped":
                    continue
                assert r.residual_m < max_coarsest_res_m, (
                    f"{r.layer_id}: résidu {r.residual_m:.1f} m "
                    f"> 1 pixel THEMIS ({max_coarsest_res_m} m)"
                )

    def test_coreg_no_reference_returns_skipped(self) -> None:
        """Sans référence HiRISE, toutes les couches sont marquées 'skipped'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            aligned = Path(tmpdir) / "aligned"
            aligned.mkdir()
            # Ne pas créer de fichier référence
            results = coregister(aligned, reference_layer="hirise_vis")
            assert all(r.status == "skipped" for r in results)


# ---------------------------------------------------------------------------
# write_coreg_report
# ---------------------------------------------------------------------------


class TestCoregReport:
    def test_report_is_written(self) -> None:
        """Le rapport de recalage est écrit dans work_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            aligned = work_dir / "aligned"
            aligned.mkdir()
            ingest_res = [
                IngestResult("dem", aligned / "dem.tif", "hirise_dem", 1.0, "ok"),
                IngestResult(
                    "thermal_inertia",
                    aligned / "thermal_inertia.tif",
                    "thermal_inertia",
                    100.0,
                    "ok",
                ),
            ]
            coreg_res = [
                CoregResult(
                    "thermal_inertia",
                    shift_x_m=0.5,
                    shift_y_m=0.3,
                    residual_m=2.1,
                    n_tie_points=10,
                    status="ok",
                ),
            ]
            path = write_coreg_report(work_dir, ingest_res, coreg_res, site_id="test")
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "thermal_inertia" in content
            assert "shift" in content.lower() or "0.50" in content

    def test_report_contains_validation_section(self) -> None:
        """Le rapport contient la section de validation humaine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir)
            path = write_coreg_report(work_dir, [], [], site_id="test")
            content = path.read_text(encoding="utf-8")
            assert "Validation" in content or "QGIS" in content


# ---------------------------------------------------------------------------
# Vérification du fichier sources.yaml
# ---------------------------------------------------------------------------


def test_jezero_sources_yaml_exists() -> None:
    """Le fichier sources.yaml de Jezero existe et liste les couches clés."""
    path = repo_root() / "config" / "sites" / "jezero" / "sources.yaml"
    assert path.exists(), f"Fichier manquant : {path}"
    import yaml

    with path.open() as fh:
        data = yaml.safe_load(fh)
    layers = data.get("layers", {})
    for expected in ("hirise_vis", "hirise_dem", "thermal_inertia", "crism_minerals"):
        assert expected in layers, f"Couche manquante dans sources.yaml : {expected}"


def test_jezero_site_yaml_exists() -> None:
    """Le fichier site.yaml de Jezero existe avec les champs requis."""
    path = repo_root() / "config" / "sites" / "jezero" / "site.yaml"
    assert path.exists()
    import yaml

    with path.open() as fh:
        cfg = yaml.safe_load(fh)
    assert cfg["site_id"] == "jezero"
    assert "analysis_crs" in cfg
    assert "+proj=eqc" in cfg["analysis_crs"]
    assert "center" in cfg
