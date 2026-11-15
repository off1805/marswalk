"""Sources d'un paquet existant, rangées comme les sorties de D1, D2 et G1 (D3).

Sert à régénérer le site fictif avec ``marswalk_pipeline.package`` et à le comparer au
paquet de T00 : ``python -m marswalk_pipeline.package fictif --from-package
fixtures/sites/fictif``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from marswalk_core.schemas import SiteManifest

ALIGNED = frozenset(
    {"hirise_vis", "ctx_vis", "dem", "dem_mola", "thermal_inertia", "crism_minerals"}
)


def export_work_dir(package: Path, work: Path) -> SiteManifest:
    """Écrit ``aligned/``, ``derived/``, ``layers/``, ``vector/`` et ``thumbs/`` dans ``work``."""
    manifest = SiteManifest.model_validate_json((package / "manifest.json").read_text("utf-8"))
    if work.exists():
        shutil.rmtree(work)
    (work / "layers").mkdir(parents=True)
    for layer in manifest.layers:
        meta = layer.model_dump(mode="json", exclude={"id", "cog", "tiles", "vector"})
        (work / "layers" / f"{layer.id}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        if layer.cog:
            sub = "aligned" if layer.id in ALIGNED else "derived"
            dst = work / sub / f"{layer.id}.tif"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package / layer.cog, dst)
        if layer.vector:
            dst = work / "vector" / f"{layer.id}.geojson"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package / layer.vector, dst)
    if (package / "thumbs").is_dir():
        shutil.copytree(package / "thumbs", work / "thumbs")
    return manifest
