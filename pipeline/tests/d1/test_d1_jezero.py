"""Tests D1 sur les données réelles de Jezero.

Ces tests s'exécutent uniquement quand les données brutes sont présentes dans
``data/raw/jezero/``. Ils sont marqués ``pytest.mark.skipif`` et ne font jamais
partie du CI standard (qui utilise le site fictif).

Couverture :
- Inspection des métadonnées source (CRS, bounds, NoData, dimensions).
- Vérification de la cohérence de la grille d'analyse Jezero.
- Reprojection individuelle de chaque couche vers la grille cible.
- Validation post-reprojection (CRS, dimensions, NoData, couverture).
- Cas particuliers : Thermal Inertia NoData=0, CRISM multi-bandes, CTX DEM lat_ts.

Lancer avec :
    uv run pytest pipeline/tests/d1/test_d1_jezero.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
import rasterio.crs

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root
from marswalk_pipeline.ingest import (
    NODATA_FLOAT,
    IngestResult,
    IngestValidation,
    _analysis_crs,
    _analysis_crs_obj,
    _check_coverage,
    _crs_needs_reprojection,
    _describe_crs,
    _make_analysis_transform,
    _probe_raster,
    _reproject_multibands_uint8,
    _reproject_with_nodata_mask,
    _select_resampling,
    reproject_to_analysis,
    validate_aligned_raster,
)

# ---------------------------------------------------------------------------
# Répertoire des données brutes Jezero
# ---------------------------------------------------------------------------

RAW_DIR = repo_root() / "data" / "raw" / "jezero"
JEZERO_DATA_AVAILABLE = RAW_DIR.is_dir() and any(RAW_DIR.iterdir())

skip_if_no_data = pytest.mark.skipif(
    not JEZERO_DATA_AVAILABLE,
    reason="Données Jezero absentes (data/raw/jezero/). Télécharger via D0.",
)

# Fichiers individuels
_FILES = {
    "hirise_dtm": RAW_DIR
    / "JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif",
    "hirise_ortho": RAW_DIR
    / "JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd.tif",
    "ctx_ortho": RAW_DIR / "JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif",
    "ctx_dem": RAW_DIR / "M20_JezeroCrater_CTXDEM_20m.tif",
    "mola_dem": RAW_DIR / "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif",
    "mola_hillshade": RAW_DIR / "Mars_MGS_MOLA_ClrShade_merge_global_463m.tif",
    "thermal": RAW_DIR / "Jezero_Thermal_Inertia_v1.tiff",
    "crism": RAW_DIR / "jezeroFinal.tif",
    "hirise_jp2_a": RAW_DIR / "ESP_046060_1985_RED.JP2",
    "hirise_jp2_b": RAW_DIR / "ESP_045994_1985_RED.JP2",
}

# CRS de référence : ESRI:103885 (EQC Mars, lat_ts=0, lon_0=0, R=3396190)
_ESRI_103885_PROJ4 = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jezero_grid() -> tuple[rasterio.transform.Affine, int, int, str]:
    cfg = load_site_config("jezero")
    transform, width, height = _make_analysis_transform(cfg)
    crs_str = _analysis_crs(cfg)
    return transform, width, height, crs_str


def _dst_crs() -> rasterio.crs.CRS:
    _, _, _, crs_str = _jezero_grid()
    return _analysis_crs_obj(crs_str)


# ---------------------------------------------------------------------------
# 1. Présence des fichiers
# ---------------------------------------------------------------------------


class TestFilesPresent:
    @skip_if_no_data
    def test_all_expected_files_present(self) -> None:
        """Les 10 fichiers attendus sont présents dans data/raw/jezero/."""
        missing = [name for name, path in _FILES.items() if not path.exists()]
        assert not missing, f"Fichiers manquants : {missing}"

    @skip_if_no_data
    @pytest.mark.parametrize("name,path", list(_FILES.items()))
    def test_file_readable_by_rasterio(self, name: str, path: Path) -> None:
        """Chaque fichier peut être ouvert par rasterio sans erreur."""
        if not path.exists():
            pytest.skip(f"{path.name} absent")
        meta = _probe_raster(path)
        assert meta["width"] > 0
        assert meta["height"] > 0


# ---------------------------------------------------------------------------
# 2. Grille d'analyse Jezero
# ---------------------------------------------------------------------------


class TestJezeroGrid:
    def test_grid_dimensions_jezero(self) -> None:
        """La grille Jezero est 5000×5000 px à 1 m/px (5 km × 5 km)."""
        transform, width, height, _ = _jezero_grid()
        assert width == 5000, f"width={width} != 5000"
        assert height == 5000, f"height={height} != 5000"

    def test_grid_resolution_1m(self) -> None:
        """La résolution de la grille est exactement 1 m/px."""
        transform, _, _, _ = _jezero_grid()
        assert abs(transform.a - 1.0) < 1e-9, f"résolution X = {transform.a}"
        assert abs(transform.e - (-1.0)) < 1e-9, f"résolution Y = {transform.e}"

    def test_grid_origin_centered(self) -> None:
        """L'origine X de la grille est -2500 m ; Y est décalé par y_center du site."""
        import math
        transform, width, height, _ = _jezero_grid()
        cfg = load_site_config("jezero")
        lat_center = float(cfg["center"]["lat"])
        R = 3_396_190.0
        y_center = lat_center * math.pi / 180.0 * R
        half = 2500.0
        # X : centré sur lon_0=77.4502 → x_center=0, coin gauche = -half
        assert abs(transform.c - (-half)) < 1e-3, f"origin X = {transform.c} (attendu {-half})"
        # Y : coin supérieur = y_center + half
        expected_f = y_center + half
        assert abs(transform.f - expected_f) < 1.0, (
            f"origin Y = {transform.f:.2f} (attendu {expected_f:.2f})"
        )

    def test_analysis_crs_is_eqc_mars(self) -> None:
        """Le CRS d'analyse est une projection EQC Mars (R=3396190)."""
        cfg = load_site_config("jezero")
        crs_str = _analysis_crs(cfg)
        assert "+proj=eqc" in crs_str, f"Pas EQC : {crs_str}"
        assert "3396190" in crs_str, f"Rayon inattendu : {crs_str}"
        assert "18.4446" in crs_str, f"lat_ts inattendu (attendu 18.4446) : {crs_str}"

    def test_grid_includes_buffer_flag_default_false(self) -> None:
        """Par défaut, grid_includes_buffer=False → grille 5000×5000, pas 6000×6000."""
        cfg = load_site_config("jezero")
        assert not cfg.get("ingest", {}).get("grid_includes_buffer", False)
        _, width, height = _make_analysis_transform(cfg)
        assert width == 5000
        assert height == 5000

    def test_grid_with_buffer_flag_enabled(self) -> None:
        """Avec grid_includes_buffer=True et buffer=500m → grille 6000×6000."""
        cfg = load_site_config("jezero")
        cfg_with_buffer = {**cfg, "ingest": {**cfg.get("ingest", {}), "grid_includes_buffer": True, "bbox_buffer_m": 500}}
        _, width, height = _make_analysis_transform(cfg_with_buffer)
        assert width == 6000, f"width={width} != 6000 avec buffer"
        assert height == 6000, f"height={height} != 6000 avec buffer"


# ---------------------------------------------------------------------------
# 3. Inspection des CRS sources
# ---------------------------------------------------------------------------


class TestSourceCRS:
    @skip_if_no_data
    def test_hirise_dtm_crs_esri_103885(self) -> None:
        """HiRISE DTM est en ESRI:103885 (EQC Mars lat_ts=0)."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        auth = meta["crs"].to_authority()
        assert auth == ("ESRI", "103885"), f"CRS inattendu : {auth} / {meta['crs_str']}"

    @skip_if_no_data
    def test_ctx_ortho_crs_esri_103885(self) -> None:
        """CTX ortho est en ESRI:103885."""
        path = _FILES["ctx_ortho"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        auth = meta["crs"].to_authority()
        assert auth == ("ESRI", "103885"), f"CRS inattendu : {auth}"

    @skip_if_no_data
    def test_hirise_ortho_crs_is_geographic(self) -> None:
        """HiRISE ortho est en CRS géographique (degrés), pas projeté."""
        path = _FILES["hirise_ortho"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        from marswalk_pipeline.ingest import _crs_is_geographic
        assert _crs_is_geographic(meta["crs"]), (
            f"HiRISE ortho attendu géographique, obtenu : {meta['crs_str']}"
        )
        # Vérifier que les bounds sont en degrés
        b = meta["bounds"]
        assert abs(b.left) < 360, f"left={b.left} hors plage degrés"
        assert abs(b.bottom) < 90, f"bottom={b.bottom} hors plage degrés"

    @skip_if_no_data
    def test_ctx_dem_crs_different_lat_ts(self) -> None:
        """CTX DEM a un lat_ts différent de 0 (18.4663°) — reprojection obligatoire."""
        path = _FILES["ctx_dem"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        proj4 = meta["crs"].to_proj4()
        assert "lat_ts" in proj4, f"Pas de lat_ts dans : {proj4}"
        # lat_ts doit être différent de 0
        for token in proj4.split():
            if token.startswith("+lat_ts="):
                lat_ts = float(token.split("=")[1])
                assert abs(lat_ts) > 1.0, f"lat_ts={lat_ts} inattendu, devrait être ~18.47"

    @skip_if_no_data
    def test_mola_hillshade_is_not_dem(self) -> None:
        """MOLA Hillshade est multi-bandes uint8 : ne pas utiliser comme DEM."""
        path = _FILES["mola_hillshade"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        # 3 bandes ou uint8 → c'est une visualisation, pas des altitudes
        assert meta["count"] == 3 or meta["dtypes"][0] == "uint8", (
            f"Hillshade inattendu : {meta['count']} bandes, {meta['dtypes']}"
        )

    @skip_if_no_data
    def test_crism_is_rgb_uint8(self) -> None:
        """CRISM jezeroFinal.tif est un raster RGB 3-bandes uint8."""
        path = _FILES["crism"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        assert meta["count"] == 3, f"CRISM : {meta['count']} bandes (attendu 3)"
        assert meta["dtypes"][0] == "uint8", f"CRISM dtype : {meta['dtypes'][0]} (attendu uint8)"

    @skip_if_no_data
    def test_thermal_nodata_is_zero(self) -> None:
        """Thermal Inertia a NoData=0.0 — doit être masqué avant reprojection."""
        path = _FILES["thermal"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        assert meta["nodata"] == 0.0, (
            f"NoData thermal inattendu : {meta['nodata']} (attendu 0.0)"
        )

    @skip_if_no_data
    def test_hirise_dtm_nodata_is_float32_max(self) -> None:
        """HiRISE DTM a NoData ≈ -3.4e38 (float32 min), pas None ni 0."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        meta = _probe_raster(path)
        nd = meta["nodata"]
        assert nd is not None, "NoData absent sur HiRISE DTM"
        assert nd < -1e30, f"NoData inattendu sur HiRISE DTM : {nd}"


# ---------------------------------------------------------------------------
# 4. Couverture sur l'emprise d'étude
# ---------------------------------------------------------------------------


class TestCoverage:
    def _grid_params(self) -> tuple:
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        return transform, width, height, dst_crs

    @skip_if_no_data
    def test_hirise_dtm_covers_study_area(self) -> None:
        """HiRISE DTM couvre entièrement la zone d'étude 5×5 km."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, dst_crs = self._grid_params()
        meta = _probe_raster(path)
        covers, fraction = _check_coverage(
            meta["bounds"], meta["crs"], transform, width, height, dst_crs
        )
        assert covers, f"HiRISE DTM ne couvre pas l'emprise (fraction={fraction:.2f})"

    @skip_if_no_data
    def test_ctx_ortho_covers_study_area(self) -> None:
        """CTX ortho couvre entièrement la zone d'étude."""
        path = _FILES["ctx_ortho"]
        if not path.exists():
            pytest.skip()
        transform, width, height, dst_crs = self._grid_params()
        meta = _probe_raster(path)
        covers, fraction = _check_coverage(
            meta["bounds"], meta["crs"], transform, width, height, dst_crs
        )
        assert covers or fraction >= 0.9, (
            f"CTX ortho couvre {fraction*100:.0f}% (attendu ≥ 90%)"
        )

    @skip_if_no_data
    def test_ctx_dem_coverage_after_crs_transform(self) -> None:
        """CTX DEM couvre la zone d'étude une fois reprojeté (CRS différent)."""
        path = _FILES["ctx_dem"]
        if not path.exists():
            pytest.skip()
        transform, width, height, dst_crs = self._grid_params()
        meta = _probe_raster(path)
        # Le CTX DEM a lat_ts=18.4663 — _check_coverage reprojette les coins
        covers, fraction = _check_coverage(
            meta["bounds"], meta["crs"], transform, width, height, dst_crs
        )
        assert fraction >= 0.5, (
            f"CTX DEM couvre {fraction*100:.0f}% après transformation (attendu ≥ 50%)"
        )

    @skip_if_no_data
    def test_mola_dem_covers_globally(self) -> None:
        """MOLA DEM est global et couvre la zone d'étude."""
        path = _FILES["mola_dem"]
        if not path.exists():
            pytest.skip()
        transform, width, height, dst_crs = self._grid_params()
        meta = _probe_raster(path)
        covers, fraction = _check_coverage(
            meta["bounds"], meta["crs"], transform, width, height, dst_crs
        )
        assert fraction >= 0.99, f"MOLA DEM fraction={fraction:.3f} (attendu ~1.0)"


# ---------------------------------------------------------------------------
# 5. Reprojection individuelle — tests unitaires
# ---------------------------------------------------------------------------


class TestReprojectionUnits:
    @skip_if_no_data
    def test_hirise_dtm_reproject_produces_correct_shape(self) -> None:
        """HiRISE DTM reprojeté sur la grille Jezero a les bonnes dimensions."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_dtm.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            assert out.exists()
            with rasterio.open(out) as ds:
                assert ds.width == width
                assert ds.height == height

    @skip_if_no_data
    def test_hirise_dtm_reproject_crs_matches_analysis(self) -> None:
        """HiRISE DTM reprojeté a le CRS d'analyse."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_dtm.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                assert not _crs_needs_reprojection(ds.crs, dst_crs), (
                    f"CRS sortie {_describe_crs(ds.crs)} != attendu {_describe_crs(dst_crs)}"
                )

    @skip_if_no_data
    def test_hirise_dtm_reproject_has_valid_pixels(self) -> None:
        """HiRISE DTM reprojeté contient des pixels valides (non-NoData)."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_dtm.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                data = ds.read(1).astype(np.float32)
                nd = ds.nodata if ds.nodata is not None else NODATA_FLOAT
                valid = np.sum(np.isfinite(data) & ~np.isclose(data, nd, rtol=0, atol=1.0))
                assert valid > 0, "Aucun pixel valide après reprojection HiRISE DTM"
                valid_pct = valid / data.size * 100
                assert valid_pct >= 50.0, (
                    f"Couverture HiRISE DTM trop faible : {valid_pct:.1f}%"
                )

    @skip_if_no_data
    def test_hirise_ortho_reproject_geographic_to_eqc(self) -> None:
        """HiRISE ortho (CRS géographique) est correctement reprojeté en EQC."""
        path = _FILES["hirise_ortho"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_ortho.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                assert not _crs_needs_reprojection(ds.crs, dst_crs)
                assert ds.width == width and ds.height == height

    @skip_if_no_data
    def test_ctx_dem_reproject_different_lat_ts(self) -> None:
        """CTX DEM (lat_ts=18.47) est correctement reprojeté malgré le CRS différent."""
        path = _FILES["ctx_dem"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "ctx_dem.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                assert not _crs_needs_reprojection(ds.crs, dst_crs)
                data = ds.read(1).astype(np.float32)
                nd = ds.nodata if ds.nodata is not None else NODATA_FLOAT
                valid = np.sum(np.isfinite(data) & ~np.isclose(data, nd, rtol=0, atol=1.0))
                assert valid > 0, "Aucun pixel valide après reprojection CTX DEM"

    @skip_if_no_data
    def test_thermal_nodata_zero_not_propagated(self) -> None:
        """Thermal Inertia : les pixels NoData=0 ne sont pas interpolés comme valeurs réelles."""
        path = _FILES["thermal"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "thermal.tif"
            _reproject_with_nodata_mask(
                path,
                out,
                crs_str,
                transform,
                width,
                height,
                resampling=rasterio.enums.Resampling.bilinear,
                src_nodata=0.0,
                dst_nodata=NODATA_FLOAT,
            )
            with rasterio.open(out) as ds:
                data = ds.read(1).astype(np.float32)
                # Le NoData de sortie doit être NODATA_FLOAT, pas 0
                assert ds.nodata == NODATA_FLOAT, f"NoData sortie = {ds.nodata}"
                # Aucun pixel ne doit avoir la valeur 0 comme vraie valeur
                # (les 0 ont été remplacés avant reprojection)
                n_zeros = int(np.sum(data == 0.0))
                assert n_zeros == 0, (
                    f"{n_zeros} pixels à 0.0 dans le Thermal Inertia reprojeté "
                    f"— ils auraient dû être masqués"
                )

    @skip_if_no_data
    def test_thermal_has_valid_nonzero_values(self) -> None:
        """Thermal Inertia contient des valeurs de thermal inertia valides après reprojection."""
        path = _FILES["thermal"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "thermal.tif"
            _reproject_with_nodata_mask(
                path,
                out,
                crs_str,
                transform,
                width,
                height,
                resampling=rasterio.enums.Resampling.bilinear,
                src_nodata=0.0,
                dst_nodata=NODATA_FLOAT,
            )
            with rasterio.open(out) as ds:
                data = ds.read(1).astype(np.float32)
                nd = NODATA_FLOAT
                valid = data[np.isfinite(data) & ~np.isclose(data, nd, rtol=0, atol=1.0)]
                assert len(valid) > 0, "Aucune valeur TI valide après reprojection"
                # Les valeurs de TI sont positives (en J/m²/K/s^0.5, typiquement 50-500)
                assert float(np.min(valid)) > 0, (
                    f"TI min = {np.min(valid):.3f} <= 0 après masquage NoData"
                )

    @skip_if_no_data
    def test_crism_multiband_reproject(self) -> None:
        """CRISM RGB 3-bandes est reprojeté en nearest neighbour sur 3 bandes uint8."""
        path = _FILES["crism"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "crism.tif"
            _reproject_multibands_uint8(
                path,
                out,
                crs_str,
                transform,
                width,
                height,
                resampling=rasterio.enums.Resampling.nearest,
                nodata=0,
            )
            assert out.exists()
            with rasterio.open(out) as ds:
                assert ds.count == 3, f"CRISM : {ds.count} bandes (attendu 3)"
                assert ds.dtypes[0] == "uint8", f"CRISM dtype : {ds.dtypes[0]} (attendu uint8)"
                assert ds.width == width and ds.height == height
                # Des pixels non-nuls doivent exister
                band1 = ds.read(1)
                assert np.any(band1 > 0), "CRISM bande 1 entièrement nulle après reprojection"

    @skip_if_no_data
    def test_mola_dem_reproject_valid(self) -> None:
        """MOLA DEM (global, int16) est reprojeté sans erreur et contient des altitudes."""
        path = _FILES["mola_dem"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "mola.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            with rasterio.open(out) as ds:
                data = ds.read(1).astype(np.float32)
                nd = ds.nodata if ds.nodata is not None else NODATA_FLOAT
                valid = data[np.isfinite(data) & ~np.isclose(data, nd, rtol=0, atol=1.0)]
                assert len(valid) > 0, "Aucun pixel valide MOLA apres reprojection"
                # Jezero est a environ -2500 m selon MOLA (par rapport a l'ellipsoide)
                # Les valeurs doivent etre dans une plage raisonnable pour cette region
                mean_elev = float(np.mean(valid))
                assert mean_elev < 0, (
                    f"Altitudes MOLA positives ({mean_elev:.0f} m) -- "
                    f"Jezero est sous le datum MOLA (~-2500 m)"
                )


# ---------------------------------------------------------------------------
# 6. Validation post-ingestion
# ---------------------------------------------------------------------------


class TestValidateAlignedRaster:
    @skip_if_no_data
    def test_validate_ok_on_good_raster(self) -> None:
        """validate_aligned_raster retourne ok=True pour un raster bien formé."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_dtm_aligned.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            result = validate_aligned_raster(
                "dem", out, dst_crs, transform, width, height
            )
            assert result.ok, f"Validation échouée : {result.issues}"
            assert result.metrics["valid_pct"] >= 50.0

    def test_validate_fails_on_missing_file(self) -> None:
        """validate_aligned_raster retourne ok=False si le fichier est absent."""
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        result = validate_aligned_raster(
            "dem",
            Path("/nonexistent/file.tif"),
            dst_crs,
            transform,
            width,
            height,
        )
        assert not result.ok
        assert any("absent" in i.lower() for i in result.issues)

    @skip_if_no_data
    def test_validate_detects_wrong_dimensions(self) -> None:
        """validate_aligned_raster détecte une grille aux mauvaises dimensions."""
        path = _FILES["hirise_dtm"]
        if not path.exists():
            pytest.skip()
        transform, width, height, crs_str = _jezero_grid()
        dst_crs = _analysis_crs_obj(crs_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "hirise_dtm_aligned.tif"
            reproject_to_analysis(path, out, crs_str, transform, width, height)
            # Valider avec des dimensions incorrectes (attendu 1000×1000 au lieu de 5000×5000)
            result = validate_aligned_raster(
                "dem", out, dst_crs, transform, 1000, 1000
            )
            assert not result.ok
            assert any("imension" in i for i in result.issues)


# ---------------------------------------------------------------------------
# 7. Rééchantillonnage adapté
# ---------------------------------------------------------------------------


class TestResamplingSelection:
    def test_crism_uses_nearest(self) -> None:
        """CRISM utilise nearest neighbour (données catégorielles)."""
        assert _select_resampling("crism_minerals") == rasterio.enums.Resampling.nearest

    def test_dem_uses_bilinear(self) -> None:
        """Les DEM utilisent le rééchantillonnage bilinéaire."""
        assert _select_resampling("dem") == rasterio.enums.Resampling.bilinear

    def test_thermal_uses_bilinear(self) -> None:
        """La thermal inertia utilise le rééchantillonnage bilinéaire."""
        assert _select_resampling("thermal_inertia") == rasterio.enums.Resampling.bilinear

    def test_hirise_vis_uses_bilinear(self) -> None:
        """L'imagerie HiRISE utilise le rééchantillonnage bilinéaire."""
        assert _select_resampling("hirise_vis") == rasterio.enums.Resampling.bilinear


# ---------------------------------------------------------------------------
# 8. Sources.yaml Jezero
# ---------------------------------------------------------------------------


def test_jezero_sources_yaml_has_all_d1_layers() -> None:
    """sources.yaml liste toutes les couches nécessaires à D1."""
    from marswalk_pipeline.ingest import _load_sources

    sources = _load_sources("jezero")
    expected = ["hirise_dem", "ctx_vis", "thermal_inertia", "crism_minerals", "dem_mola"]
    missing = [k for k in expected if k not in sources]
    assert not missing, f"Clés manquantes dans sources.yaml : {missing}"


def test_jezero_site_yaml_analysis_crs_centered_on_jezero() -> None:
    """Le CRS d'analyse est centré sur les coordonnées de Jezero (77.4502°, 18.4446°)."""
    cfg = load_site_config("jezero")
    crs_str = _analysis_crs(cfg)
    assert "77.4502" in crs_str, f"lon_0 inattendu dans : {crs_str}"
    assert "18.4446" in crs_str, f"lat_ts inattendu dans : {crs_str}"


def test_jezero_site_yaml_size_5km() -> None:
    """La zone d'étude fait 5000 m × 5000 m."""
    cfg = load_site_config("jezero")
    assert cfg["size_m"] == 5000, f"size_m = {cfg['size_m']} (attendu 5000)"


def test_jezero_site_yaml_resolution_1m() -> None:
    """La résolution cible est 1 m/px."""
    cfg = load_site_config("jezero")
    assert cfg["resolution_m"] == 1.0, f"resolution_m = {cfg['resolution_m']} (attendu 1.0)"
