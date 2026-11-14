"""Lecture dégradée des couches géospatiales pour P1.

Règles (ENF-07) :
- Une couche ``missing`` ou absente du manifeste ne lève pas d'exception : on retourne
  ``None`` et on enregistre un avertissement.
- Une couche ``degraded`` est lue normalement, mais un avertissement signale la fiabilité
  réduite.
- On ne transforme jamais l'inconnu en sûr : quand une couche est absente, les masques
  qui en dépendent appliquent la marge de sécurité accrue (``degraded_margin_pct``).

Couches indispensables et leurs rôles dans P1 :
  slope           → zones interdites (pente > seuil) et pénalisées (pente intermédiaire)
  obstacles       → zones interdites
  scarps          → zones interdites (tampon de falaise)
  loose_soil      → zones interdites (dunes, classe 3) et pénalisées (classe 2)
  thermal_inertia → améliore la fiabilité de loose_soil ; si absente, avertissement
  radio_coverage  → zones pénalisées
  illumination    → zones pénalisées
  roughness       → pénalité de terrain
  crism_minerals  → intérêt scientifique (réduction de coût)
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from marswalk_core.schemas import LayerStatus
from marswalk_core.site_package import LayerUnavailableError, Site

logger = logging.getLogger(__name__)

FloatGrid = NDArray[np.float32]


@dataclass
class LayerBundle:
    """Ensemble des tableaux numpy nécessaires à P1, avec leur statut et les avertissements."""

    slope: FloatGrid
    """Pente en degrés. NaN remplacé par 90.0 (pire cas) quand la couche est absente."""
    obstacles: FloatGrid
    """Masque binaire 0/1. NaN → 1.0 (pire cas) si absent."""
    scarps: FloatGrid
    """Masque binaire 0/1. NaN → 1.0 (pire cas) si absent."""
    loose_soil: FloatGrid
    """Classe de sol 0-3. NaN → 3.0 (dune, pire cas) si absent."""
    radio_coverage: FloatGrid | None
    """Fraction de couverture radio 0/1. None si couche absente."""
    illumination: FloatGrid | None
    """Fraction d'éclairement 0-1. None si couche absente."""
    roughness: FloatGrid | None
    """Rugosité en mètres. None si couche absente."""
    crism_minerals: FloatGrid | None
    """Indice minéralogique 0-2. None si couche absente."""
    warnings: list[str] = field(default_factory=list)
    degraded_layers: list[str] = field(default_factory=list)


def _read_or_none(site: Site, layer_id: str, warnings_out: list[str]) -> FloatGrid | None:
    """Lit un tableau numpy, retourne None si la couche est indisponible.

    Retourne une vue (pas de copie) si possible ; les opérations en aval
    n'écrivent jamais dans ce tableau (read-only).
    """
    try:
        info = site.layer(layer_id)
    except LayerUnavailableError:
        warnings_out.append(
            f"Couche absente du manifeste : {layer_id!r}. "
            "Les calculs qui en dépendent appliquent la marge de sécurité accrue."
        )
        return None

    if info.status == LayerStatus.missing or info.cog is None:
        warnings_out.append(
            f"Couche {layer_id!r} marquée 'missing'. "
            "Les calculs qui en dépendent appliquent la marge de sécurité accrue."
        )
        return None

    # read_layer met en cache dans site._cache ; .values est le ndarray interne.
    # On prend une vue float32 sans copie.
    arr: np.ndarray = site.read_layer(layer_id).values

    if info.status == LayerStatus.degraded:
        warnings_out.append(
            f"Couche {layer_id!r} marquée 'degraded' "
            f"(note: {info.status_note or 'aucune'}). "
            "Résultats moins fiables sur cette couche."
        )

    return arr.astype(np.float32, copy=False)


def _fill_nan(arr: FloatGrid, fill: float) -> FloatGrid:
    """Remplace les NaN par ``fill`` si nécessaire, sans copie superflue."""
    if not bool(np.any(np.isnan(arr))):
        return arr
    return np.where(np.isnan(arr), fill, arr).astype(np.float32)


def load_layers(site: Site) -> LayerBundle:
    """Charge toutes les couches nécessaires à P1 avec dégradation gracieuse.

    Les couches critiques (slope, obstacles, scarps, loose_soil) voient leur nodata
    remplacé par la valeur de pire cas plutôt que d'être ignorées, afin de ne jamais
    présenter une zone inconnue comme sûre.
    """
    warn: list[str] = []
    degraded: list[str] = []

    # --- couches critiques ------------------------------------------------

    slope_raw = _read_or_none(site, "slope", warn)
    if slope_raw is None:
        warn.append(
            "Couche 'slope' absente : toutes les cases sont traitées comme à 90° (tout interdit)."
        )
        slope = np.full(site.shape, 90.0, dtype=np.float32)
        degraded.append("slope")
    else:
        slope = _fill_nan(slope_raw, 90.0)
        try:
            if site.layer("slope").status == LayerStatus.degraded:
                degraded.append("slope")
        except LayerUnavailableError:
            pass

    obstacles_raw = _read_or_none(site, "obstacles", warn)
    if obstacles_raw is None:
        warn.append(
            "Couche 'obstacles' absente : toutes les cases sont traitées comme "
            "potentiellement obstruées (marge accrue)."
        )
        obstacles = np.ones(site.shape, dtype=np.float32)
        degraded.append("obstacles")
    else:
        obstacles = _fill_nan(obstacles_raw, 1.0)
        try:
            if site.layer("obstacles").status == LayerStatus.degraded:
                degraded.append("obstacles")
        except LayerUnavailableError:
            pass

    scarps_raw = _read_or_none(site, "scarps", warn)
    if scarps_raw is None:
        warn.append(
            "Couche 'scarps' absente : zones de rupture de pente non détectables. "
            "Tampon de falaise étendu appliqué sur toutes les pentes fortes."
        )
        scarps = np.zeros(site.shape, dtype=np.float32)
        degraded.append("scarps")
    else:
        scarps = _fill_nan(scarps_raw, 1.0)
        try:
            if site.layer("scarps").status == LayerStatus.degraded:
                degraded.append("scarps")
        except LayerUnavailableError:
            pass

    # thermal_inertia améliore loose_soil ; si absent, on avertit avant de lire loose_soil
    thermal_raw = _read_or_none(site, "thermal_inertia", warn)
    if thermal_raw is None:
        warn.append(
            "Couche 'thermal_inertia' absente : l'évaluation des dunes et des sols "
            "meubles repose uniquement sur 'loose_soil' (moins fiable). "
            "Marge de sécurité accrue appliquée sur la classification des sols."
        )
        degraded.append("thermal_inertia")

    loose_soil_raw = _read_or_none(site, "loose_soil", warn)
    if loose_soil_raw is None:
        warn.append(
            "Couche 'loose_soil' absente : tous les sols sont traités comme des dunes "
            "(classe 3, pire cas)."
        )
        loose_soil = np.full(site.shape, 3.0, dtype=np.float32)
        degraded.append("loose_soil")
    else:
        loose_soil = _fill_nan(loose_soil_raw, 3.0)
        try:
            if site.layer("loose_soil").status == LayerStatus.degraded:
                degraded.append("loose_soil")
        except LayerUnavailableError:
            pass

    # --- couches secondaires (pénalités) ----------------------------------

    radio_raw = _read_or_none(site, "radio_coverage", warn)
    radio: FloatGrid | None = None
    if radio_raw is not None:
        radio = _fill_nan(radio_raw, 0.0)
        try:
            if site.layer("radio_coverage").status == LayerStatus.degraded:
                degraded.append("radio_coverage")
        except LayerUnavailableError:
            pass

    illum_raw = _read_or_none(site, "illumination", warn)
    illum: FloatGrid | None = None
    if illum_raw is not None:
        illum = _fill_nan(illum_raw, 0.0)
        try:
            if site.layer("illumination").status == LayerStatus.degraded:
                degraded.append("illumination")
        except LayerUnavailableError:
            pass

    roughness_raw = _read_or_none(site, "roughness", warn)
    roughness: FloatGrid | None = None
    if roughness_raw is not None:
        roughness = _fill_nan(roughness_raw, 0.0)
        try:
            if site.layer("roughness").status == LayerStatus.degraded:
                degraded.append("roughness")
        except LayerUnavailableError:
            pass

    crism_raw = _read_or_none(site, "crism_minerals", warn)
    crism: FloatGrid | None = None
    if crism_raw is not None:
        crism = _fill_nan(crism_raw, 0.0)
        try:
            if site.layer("crism_minerals").status == LayerStatus.degraded:
                degraded.append("crism_minerals")
        except LayerUnavailableError:
            pass

    # Émettre vers le système de logs en plus de retourner les avertissements
    for w in warn:
        logger.warning("P1 layers: %s", w)
        warnings.warn(w, stacklevel=4)

    return LayerBundle(
        slope=slope,
        obstacles=obstacles,
        scarps=scarps,
        loose_soil=loose_soil,
        radio_coverage=radio,
        illumination=illum,
        roughness=roughness,
        crism_minerals=crism,
        warnings=warn,
        degraded_layers=degraded,
    )
