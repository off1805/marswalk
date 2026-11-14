"""Tests unitaires et d'intégration pour le service site_layers (Sites, Couches, Interrogation)."""

import pytest
from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.site_layers.data_source import MockSiteDataSource, PackageSiteDataSource
from marswalk_api.services.site_layers.services import PointQueryService, SiteCatalogService

client = TestClient(app)


def test_list_sites() -> None:
    res = client.get("/api/sites")
    assert res.status_code == 200
    sites = res.json()
    assert isinstance(sites, list)
    assert any(s["site_id"] == "fictif" for s in sites)


def test_get_site_manifest_success() -> None:
    res = client.get("/api/sites/fictif")
    assert res.status_code == 200
    manifest = res.json()
    assert manifest["site_id"] == "fictif"
    assert "layers" in manifest
    assert len(manifest["layers"]) > 0


def test_get_site_manifest_not_found() -> None:
    res = client.get("/api/sites/unknown_site")
    assert res.status_code == 404
    assert "Site inconnu" in res.json()["detail"]


def test_list_presets() -> None:
    res = client.get("/api/presets")
    assert res.status_code == 200
    presets = res.json()
    assert isinstance(presets, list)
    preset_ids = [p["id"] for p in presets]
    assert "safety" in preset_ids or "science" in preset_ids


def test_query_point_valid() -> None:
    res = client.get("/api/sites/fictif/query?lon=77.58&lat=18.38")
    assert res.status_code == 200
    data = res.json()
    assert data["site_id"] == "fictif"
    assert "values" in data
    assert len(data["values"]) > 0
    assert "return_time_s" in data
    assert data["return_time_s"] is not None

    slope_layer = next((v for v in data["values"] if v["layer_id"] == "slope"), None)
    assert slope_layer is not None
    assert slope_layer["status"] in ("ok", "degraded", "missing")
    assert "source" in slope_layer


def test_query_point_out_of_bounds() -> None:
    res = client.get("/api/sites/fictif/query?lon=0.0&lat=0.0")
    assert res.status_code == 400
    assert "hors de l'emprise" in res.json()["detail"]


def test_tiles_served_and_cache_headers() -> None:
    res = client.get("/tiles/fictif/hirise_vis/16/59239/29676.webp")
    if res.status_code == 200:
        assert res.headers["content-type"] == "image/webp"
        assert "Cache-Control" in res.headers
        assert "max-age" in res.headers["Cache-Control"]

    res_404 = client.get("/tiles/fictif/hirise_vis/99/99/99.webp")
    assert res_404.status_code == 404


def test_mock_data_source_behavior() -> None:
    mock_src = MockSiteDataSource()
    service = PointQueryService(mock_src)
    query = service.query_point("fictif", 77.58, 18.38)
    assert query.site_id == "fictif"
    assert len(query.values) > 0
