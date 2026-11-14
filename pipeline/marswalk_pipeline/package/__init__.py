"""Paquet de site (D3) : COG, tuiles d'affichage, terrain-RGB et manifeste.

``build_package(site_id)`` lit ``data/work/<site_id>/`` et écrit ``data/packages/<site_id>/``,
puis le valide avec ``tools/validate_site_package.py``. Commande :
``python -m marswalk_pipeline.package <site_id>``.
"""

from .build import (
    MAX_BYTES,
    PackageError,
    PackageInvalidError,
    PackageReport,
    PackageTooLargeError,
    build_package,
    default_out_dir,
    default_work_dir,
)

__all__ = [
    "MAX_BYTES",
    "PackageError",
    "PackageInvalidError",
    "PackageReport",
    "PackageTooLargeError",
    "build_package",
    "default_out_dir",
    "default_work_dir",
]
