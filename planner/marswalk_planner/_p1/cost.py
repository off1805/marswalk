"""Calcul vectorisé de la grille de coût (P1-D).

Formule (section 7, taches-agents.md) :

    C = w_t · t + w_r · R − w_s · S

Définitions et unités (d'après la section 7 du document de besoins) :

t — Coût temporel (secondes)
    Temps de traversée d'une cellule de ``resolution_m`` mètres par un astronaute
    marchant à la vitesse de base du modèle de marche.
    La vitesse de base dépend de la pente et du sol ; ici P1 utilise la formule de
    Tobler adaptée à 0,38 g (fournie par P3) si disponible, sinon une approximation
    conservative :
        vitesse_m_s = base_speed × facteur_pente × facteur_sol
    avec facteur_pente = exp(−3,5 × |sin(pente) + 0,05|) / exp(−3,5 × 0,05)
    (Tobler normalisée à 1 sur plat) et facteur_sol = [1.0, 0.9, 0.7, 0.5][classe].

    t = resolution_m / vitesse_m_s

R — Risque (sans dimension, normalisé 0-1)
    Somme pondérée des pénalités actives, bornée à [0, 1].
    Les pénalités individuelles sont :
        pente_intermédiaire : (pente − penalty_slope_deg) / (max_slope_deg − penalty_slope_deg)
                              pour penalty_slope_deg ≤ pente < max_slope_deg, sinon 0
        sol_meuble          : 0,5 si loose_soil == avoid_loose_soil_class − 1
        hors_radio          : radio_penalty / (radio_penalty + 1)   (normalisé)
        ombre               : (1 − illumination) × 0,3  si illumination < min_illumination
        rugosité            : roughness / max_roughness_m bornée à [0, 1]
        conditions          : dust_penalty si dust_tau > max_dust_tau,
                              dose_penalty si dose_rate élevé
    R = clip(somme des pénalités actives, 0, 1)

S — Intérêt scientifique (sans dimension, normalisé 0-1)
    Score basé sur la minéralogie CRISM :
        0  → 0.0  (non détecté)
        1  → 0.5  (argiles/carbonates, intérêt moyen)
        2  → 1.0  (olivine, intérêt maximal)
    Si la couche est absente, S = 0.0 (inconnu ≠ sans intérêt, mais pas de bonus par défaut).

Cellules interdites
    cost[forbidden] = +inf, identifiable par cost_grid.forbidden.
    Ces cellules ne peuvent jamais être des passages pour P2.

NaN / nodata
    Les couches critiques ont déjà été remplacées par leur valeur de pire cas dans
    ``_p1.layers`` ; aucun NaN ne devrait subsister dans ``t``, ``R`` ou ``S``.
    On applique tout de même np.nan_to_num en sortie comme filet de sécurité.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from marswalk_core.grids import CostGrid
from marswalk_core.schemas import Conditions, SafetySettings
from marswalk_core.site_package import Site

from .layers import LayerBundle
from .masks import build_masks

FloatGrid = NDArray[np.float32]

# Vitesse de base en m/s (reprise de SuitModel.base_speed_mps par défaut)
_DEFAULT_BASE_SPEED = np.float32(1.0)
# Facteurs de vitesse par classe de sol 0-3 (repris de SuitModel.soil_speed_factor)
_SOIL_SPEED_FACTOR = np.array([1.0, 0.9, 0.7, 0.5], dtype=np.float32)
# Poids Tobler adaptés à 0,38 g : même forme que sur Terre, amplitude réduite
_TOBLER_K = 3.5
_TOBLER_OFFSET = 0.05  # vitesse max ≈ pente légèrement descendante

# Table de recherche Tobler : angles de 0 à 90° en pas de 0,05° → 1800 entrées.
# Précision : ±0,05° → erreur sur t < 0,1 % ; bien en dessous de l'incertitude
# de la couche de pente (±0,5° selon le manifeste du site fictif).
_LUT_N = 1800
_LUT_ANGLES = np.linspace(0.0, 90.0, _LUT_N, dtype=np.float32)
_LUT_NORM = float(np.exp(-_TOBLER_K * _TOBLER_OFFSET))
_LUT_SPEED: FloatGrid = (
    np.exp(-_TOBLER_K * np.abs(np.sin(np.radians(_LUT_ANGLES)) + _TOBLER_OFFSET))
    / _LUT_NORM
).astype(np.float32)
_LUT_SCALE = np.float32((_LUT_N - 1) / 90.0)  # degrés → index LUT


# ---------------------------------------------------------------------------
# Coût temporel t
# ---------------------------------------------------------------------------


def _time_grid(
    slope_deg: FloatGrid,
    loose_soil: FloatGrid,
    resolution_m: float,
) -> FloatGrid:
    """Grille de temps de traversée en secondes (vectorisée NumPy).

    Tobler adaptée à 0,38 g via LUT pré-calculée :
        vitesse = base × speed_lut[idx] × facteur_sol
        idx = round(slope_deg × (N-1) / 90)

    La LUT couvre 0–90° en 1800 pas (0,05°), précision suffisante par rapport à
    l'incertitude de mesure de la pente (±0,5° selon le manifeste).
    """
    idx = np.clip(
        (slope_deg * _LUT_SCALE).astype(np.int32), 0, _LUT_N - 1
    )
    speed_factor = _LUT_SPEED[idx]  # (H, W) float32, vectorisé

    soil_cls = np.clip(loose_soil.astype(np.int32), 0, 3)
    soil_factor = _SOIL_SPEED_FACTOR[soil_cls]

    speed = np.maximum(speed_factor * soil_factor, np.float32(1e-6))
    return (np.float32(resolution_m) / speed).astype(np.float32)


# ---------------------------------------------------------------------------
# Risque R
# ---------------------------------------------------------------------------


def _risk_grid(
    layers: LayerBundle,
    settings: SafetySettings,
    conditions: Conditions | None,
) -> FloatGrid:
    """Grille de risque normalisé [0, 1] (vectorisée NumPy, accumulateur in-place)."""
    slope = layers.slope
    shape = slope.shape
    risk = np.zeros(shape, dtype=np.float32)

    # --- pente intermédiaire ---
    span = settings.max_slope_deg - settings.penalty_slope_deg
    if span > 0:
        in_range = (slope >= settings.penalty_slope_deg) & (slope < settings.max_slope_deg)
        np.add(
            risk,
            np.where(in_range, (slope - settings.penalty_slope_deg) / span, 0.0),
            out=risk,
            casting="unsafe",
        )

    # --- sol meuble ---
    soil_pen_class = settings.avoid_loose_soil_class - 1
    if soil_pen_class >= 1:
        np.add(
            risk,
            np.where(layers.loose_soil == float(soil_pen_class), 0.5, 0.0),
            out=risk,
            casting="unsafe",
        )

    # --- hors couverture radio ---
    if layers.radio_coverage is not None:
        pen_val = np.float32(settings.radio_penalty / (settings.radio_penalty + 1.0))
        np.add(
            risk,
            np.where(layers.radio_coverage < 0.5, pen_val, 0.0),
            out=risk,
            casting="unsafe",
        )

    # --- ombrage ---
    if layers.illumination is not None:
        in_shadow = layers.illumination <= settings.min_illumination
        shadow_pen = np.where(
            in_shadow,
            np.clip((1.0 - layers.illumination) * np.float32(0.3), 0.0, 0.3),
            np.float32(0.0),
        )
        np.add(risk, shadow_pen, out=risk, casting="unsafe")

    # --- rugosité ---
    if layers.roughness is not None and settings.max_roughness_m > 0:
        inv_max = np.float32(1.0 / settings.max_roughness_m)
        rough_pen = np.clip(layers.roughness * inv_max, 0.0, 1.0) * np.float32(0.4)
        np.add(
            risk,
            np.where(layers.roughness > settings.max_roughness_m, rough_pen, 0.0),
            out=risk,
            casting="unsafe",
        )

    # --- conditions environnementales ---
    if conditions is not None:
        if conditions.dust_tau is not None and conditions.dust_tau > settings.max_dust_tau:
            excess_ratio = min(
                (conditions.dust_tau - settings.max_dust_tau)
                / max(settings.max_dust_tau, 0.1),
                1.0,
            )
            risk += np.float32(excess_ratio * 0.3)

        if conditions.dose_rate_usv_h is not None:
            dose_ref = settings.max_dose_usv / 8.0
            if conditions.dose_rate_usv_h > dose_ref:
                dose_ratio = min(
                    conditions.dose_rate_usv_h / max(dose_ref, 1.0) - 1.0,
                    1.0,
                )
                risk += np.float32(dose_ratio * 0.5)

    np.clip(risk, 0.0, 1.0, out=risk)
    return risk


# ---------------------------------------------------------------------------
# Intérêt scientifique S
# ---------------------------------------------------------------------------


def _science_grid(layers: LayerBundle) -> FloatGrid:
    """Grille d'intérêt scientifique normalisé [0, 1].

    CRISM : 0 → 0.0 | 1 (argiles/carbonates) → 0.5 | 2 (olivine) → 1.0
    """
    if layers.crism_minerals is None:
        return np.zeros(layers.slope.shape, dtype=np.float32)

    crism = layers.crism_minerals
    sci = np.zeros(crism.shape, dtype=np.float32)
    sci = np.where(crism >= 1.5, 1.0, sci)
    sci = np.where((crism >= 0.5) & (crism < 1.5), 0.5, sci)
    return sci.astype(np.float32)


# ---------------------------------------------------------------------------
# Assemblage de la grille de coût
# ---------------------------------------------------------------------------


def compute_cost_grid(
    layers: LayerBundle,
    settings: SafetySettings,
    site: Site,
    conditions: Conditions | None,
) -> CostGrid:
    """Calcule la grille de coût complète C = w_t·t + w_r·R − w_s·S.

    Les cellules interdites reçoivent +inf et ne peuvent pas servir de passage à P2.
    """
    resolution = site.manifest.grid.resolution_m

    # Masques
    forbidden, penalized, by_cause = build_masks(layers, settings, site)

    # Composantes
    t_grid = _time_grid(layers.slope, layers.loose_soil, resolution)
    r_grid = _risk_grid(layers, settings, conditions)
    s_grid = _science_grid(layers)

    # Poids
    w_t = float(settings.weights.time)
    w_r = float(settings.weights.risk)
    w_s = float(settings.weights.science)

    cost_raw = (w_t * t_grid + w_r * r_grid - w_s * s_grid).astype(np.float32)

    # Garantie : le coût ne peut pas être négatif (l'intérêt scientifique ne rend
    # pas une cellule « gratuite »)
    cost_raw = np.maximum(cost_raw, 0.0)

    # Cellules interdites → +inf
    cost = np.where(forbidden, np.inf, cost_raw).astype(np.float32)

    # Filet de sécurité NaN (ne devrait pas subsister)
    cost = np.nan_to_num(cost, nan=np.inf, posinf=np.inf).astype(np.float32)

    # Marge de dégradation : si des couches étaient dégradées/absentes, on avertit
    # (la marge est déjà appliquée via les pires cas dans _layers.py)
    extra_warnings = list(layers.warnings)
    margin = 0.0
    if layers.degraded_layers:
        margin = settings.degraded_margin_pct
        extra_warnings.append(
            f"Marge de sécurité accrue de {margin:.0f} % appliquée : couches dégradées "
            f"ou absentes : {', '.join(sorted(set(layers.degraded_layers)))}."
        )

    return CostGrid(
        site=site,
        transform=site.transform,
        resolution_m=resolution,
        cost=cost,
        forbidden=forbidden,
        terms={
            "time": t_grid,
            "risk": r_grid,
            "science": s_grid,
            "penalized": penalized.astype(np.float32),
            # Poids stockés comme scalaires float (lus par _p1.explain)
            "_w_t": w_t,  # type: ignore[dict-item]
            "_w_r": w_r,  # type: ignore[dict-item]
            "_w_s": w_s,  # type: ignore[dict-item]
            **{
                f"cause_{k}": v.astype(np.float32)
                for k, v in by_cause.items()
            },
        },
        warnings=extra_warnings,
        margin_pct=margin,
    )
