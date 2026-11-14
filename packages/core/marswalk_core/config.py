"""Lecture des fichiers de ``config/`` (sécurité, combinaison, préréglages, sites)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from marswalk_core.paths import config_dir
from marswalk_core.schemas import DisplayPreset, SafetySettings, SuitModel


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} doit contenir un objet YAML")
    return data


def load_safety_presets() -> dict[str, SafetySettings]:
    """Préréglages de sécurité de ``config/safety.yaml``, indexés par nom."""
    data = _read_yaml(config_dir() / "safety.yaml")
    return {
        name: SafetySettings.model_validate({"preset": name, **values})
        for name, values in data["presets"].items()
    }


def load_safety_settings(preset: str | None = None) -> SafetySettings:
    data = _read_yaml(config_dir() / "safety.yaml")
    name = preset or str(data["default"])
    presets = load_safety_presets()
    if name not in presets:
        raise KeyError(f"Préréglage de sécurité inconnu : {name}")
    return presets[name]


def load_suit(name: str | None = None) -> SuitModel:
    data = _read_yaml(config_dir() / "suit.yaml")
    key = name or str(data["default"])
    return SuitModel.model_validate({"name": key, **data["suits"][key]})


def load_display_presets() -> list[DisplayPreset]:
    data = _read_yaml(config_dir() / "presets.yaml")
    return [DisplayPreset.model_validate({"id": k, **v}) for k, v in data["presets"].items()]


def load_site_config(site_id: str) -> dict[str, Any]:
    """Configuration d'entrée du pipeline : ``config/sites/<site_id>/site.yaml``."""
    return _read_yaml(config_dir() / "sites" / site_id / "site.yaml")
