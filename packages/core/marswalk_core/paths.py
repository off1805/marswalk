"""Emplacements du dépôt, des configurations et des paquets de site."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Racine du monorepo : ``MARSWALK_ROOT`` ou premier parent qui contient ``config/``."""
    env = os.environ.get("MARSWALK_ROOT")
    if env:
        return Path(env).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "config").is_dir() and (parent / "fixtures").is_dir():
            return parent
    return Path.cwd().resolve()


def config_dir() -> Path:
    return Path(os.environ.get("MARSWALK_CONFIG_DIR", repo_root() / "config"))


def package_search_path() -> list[Path]:
    """Dossiers où chercher ``<site_id>/manifest.json``, dans l'ordre.

    ``MARSWALK_PACKAGES`` (liste séparée par ``:``) sinon ``data/packages`` puis
    ``fixtures/sites``. Le premier paquet trouvé l'emporte.
    """
    env = os.environ.get("MARSWALK_PACKAGES")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    root = repo_root()
    return [root / "data" / "packages", root / "fixtures" / "sites"]


def find_package(site_id: str) -> Path:
    for base in package_search_path():
        candidate = base / site_id
        if (candidate / "manifest.json").is_file():
            return candidate
    raise FileNotFoundError(f"Paquet de site introuvable : {site_id}")


def list_package_ids() -> list[str]:
    ids: list[str] = []
    for base in package_search_path():
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (child / "manifest.json").is_file() and child.name not in ids:
                ids.append(child.name)
    return ids
