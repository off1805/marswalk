"""Outils de T00 : contrôle de propriété, export des contrats, validateur de paquet."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_ownership  # noqa: E402
import export_contracts  # noqa: E402
import validate_site_package  # noqa: E402


def test_out_of_scope_file_fails() -> None:
    rc = check_ownership.main(
        ["--branch", "task/P1-risque", "--files", "planner/marswalk_planner/route.py"]
    )
    assert rc == 1


def test_contract_file_is_frozen_for_tasks() -> None:
    own = check_ownership.Ownership.load()
    assert own.check("F2", ["web/src/shared/store.ts"]) == ["web/src/shared/store.ts"]
    assert own.check("A2", ["api/marswalk_api/db/migrations/versions/0002_x.py"])
    assert own.check("P2", ["packages/core/marswalk_core/schemas.py"])


def test_in_scope_files_pass() -> None:
    rc = check_ownership.main(
        [
            "--branch",
            "task/P1-risque",
            "--files",
            "planner/marswalk_planner/cost.py",
            "planner/tests/p1/README.md",
            "config/safety.yaml",
            "uv.lock",
            "tasks/change-requests/P1-seuils.md",
        ]
    )
    assert rc == 0


def test_exclusions_and_other_branches() -> None:
    own = check_ownership.Ownership.load()
    assert own.check("D1", ["config/sites/jezero/targets-seed.geojson"])
    assert not own.check("S1", ["config/sites/jezero/targets-seed.geojson"])
    assert check_ownership.main(["--branch", "main", "--files", "x"]) == 0


def test_every_task_has_paths() -> None:
    own = check_ownership.Ownership.load()
    expected = {
        "T00",
        "C1",
        "D1",
        "D2",
        "D3",
        "P1",
        "P2",
        "P3",
        "K1",
        "A1",
        "A2",
        "A3",
        "A4",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7",
        "S1",
        "G1",
        "X1",
        "I1",
        "I2",
        "L1",
        "L2",
        "X2",
        "X3",
        "X4",
    }
    assert set(own.tasks) == expected


def test_openapi_export_matches_versioned_file() -> None:
    for path, text in export_contracts.exports().items():
        assert path.read_text(encoding="utf-8") == text, f"{path} diffère de l'export"


def test_fictif_package_is_valid() -> None:
    assert validate_site_package.validate(ROOT / "fixtures/sites/fictif", 30_000_000) == []


def test_validator_rejects_broken_package(tmp_path: Path) -> None:
    pkg = tmp_path / "fictif"
    shutil.copytree(ROOT / "fixtures/sites/fictif", pkg)
    (pkg / "cog" / "slope.tif").unlink()
    manifest = json.loads((pkg / "manifest.json").read_text())
    manifest["bbox"] = [200, 0, 10, 1]
    (pkg / "manifest.json").write_text(json.dumps(manifest))
    errors = validate_site_package.validate(pkg)
    assert any("slope" in e for e in errors)
    assert any("bbox" in e for e in errors)


@pytest.mark.parametrize("limit", [1000])
def test_validator_enforces_size(limit: int) -> None:
    errors = validate_site_package.validate(ROOT / "fixtures/sites/fictif", limit)
    assert any("taille" in e for e in errors)
