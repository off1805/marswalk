"""Route des images au sol (G1) sur le paquet du site fictif."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_core.paths import repo_root
from marswalk_core.site_package import clear_cache

client = TestClient(app)


def test_site_images_come_from_the_package() -> None:
    res = client.get("/api/sites/fictif/ground-images")
    assert res.status_code == 200, res.text
    expected = json.loads(
        (repo_root() / "fixtures/sites/fictif/vector/ground_images.geojson").read_text("utf-8")
    )
    assert [f["id"] for f in res.json()["features"]] == [f["id"] for f in expected["features"]]
    for f in res.json()["features"]:
        p = f["properties"]
        assert isinstance(p["sol"], int) and p["instrument"] and p["image_id"]


def test_unknown_site_is_404() -> None:
    assert client.get("/api/sites/inconnu/ground-images").status_code == 404


def test_package_without_images_gives_an_empty_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = repo_root() / "fixtures/sites/fictif"
    dst = tmp_path / "fictif"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("tiles", "thumbs"))
    (dst / "vector" / "ground_images.geojson").unlink()
    monkeypatch.setenv("MARSWALK_PACKAGES", str(tmp_path))
    clear_cache()
    try:
        res = client.get("/api/sites/fictif/ground-images")
    finally:
        clear_cache()
    assert res.status_code == 200 and res.json()["features"] == []
