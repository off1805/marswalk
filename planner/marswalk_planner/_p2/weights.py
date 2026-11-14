"""Jeux de poids pour les trois variantes d'itinéraire (P2-E).

Chaque variante repose sur un ``SafetySettings`` modifié dont les poids
CostWeights sont ajustés. Les valeurs nominales viennent du settings passé
par le appelant (issu de config/safety.yaml) et sont sur-pondérées selon la
variante.

Cohérence avec la formule de P1 :
    C = w_t · t + w_r · R − w_s · S

Safest :
  - Privilégier la réduction du risque : w_r élevé, w_t réduit.
  - Marges de sécurité accrues : seuils plus stricts.
  - Poids science réduit (priorité sécurité).

Fastest :
  - Privilégier le temps de déplacement : w_t élevé, w_r réduit (mais non nul).
  - Marges nominales, pas de relaxation des interdictions.

Science :
  - Favoriser l'intérêt scientifique : w_s élevé, compromis w_t/w_r équilibré.
  - Les cibles à fort intérêt bénéficient de la réduction de coût.

Les trois variantes produisent des chemins différents si :
  - Le terrain présente des zones à risque variable (pentes intermédiaires, hors radio…)
  - Ou des zones CRISM à fort intérêt scientifique.
  - Sur un terrain totalement uniforme (plateau plat sans intérêt), elles convergent :
    c'est normal et attendu.

Remarque : on ne fabrique pas artificiellement des différences. Si la
configuration du terrain ne les justifie pas, les itinéraires sont identiques.
"""

from __future__ import annotations

import copy

from marswalk_core.schemas import CostWeights, SafetySettings

# Facteurs multiplicatifs par rapport aux poids nominaux
# (w_t_nom, w_r_nom, w_s_nom) du settings fourni

_SAFEST_FACTORS = dict(time=0.5, risk=3.0, science=0.3)
"""Safest : risque dominant, temps secondaire, science minimisée."""

_FASTEST_FACTORS = dict(time=3.0, risk=0.5, science=0.2)
"""Fastest : temps dominant, risque atténué (interdit reste interdit)."""

_SCIENCE_FACTORS = dict(time=1.0, risk=1.0, science=4.0)
"""Science : intérêt scientifique fortement amplifié, reste équilibré."""


def _apply_factors(base: SafetySettings, factors: dict[str, float]) -> SafetySettings:
    """Crée un SafetySettings avec les poids ajustés."""
    s = copy.deepcopy(base)
    s.weights = CostWeights(
        time=base.weights.time * factors["time"],
        risk=base.weights.risk * factors["risk"],
        science=base.weights.science * factors["science"],
    )
    return s


def safest_settings(base: SafetySettings) -> SafetySettings:
    """SafetySettings pour la variante Safest.

    En plus des poids, le seuil de pénalité de pente est abaissé de 15 %
    pour anticiper davantage les zones à risque modéré.
    """
    s = _apply_factors(base, _SAFEST_FACTORS)
    # Seuil de pénalité légèrement plus strict
    s.penalty_slope_deg = max(1.0, base.penalty_slope_deg * 0.85)
    return s


def fastest_settings(base: SafetySettings) -> SafetySettings:
    """SafetySettings pour la variante Fastest.

    Les interdictions absolues restent inchangées. Seuls les poids changent.
    """
    return _apply_factors(base, _FASTEST_FACTORS)


def science_settings(base: SafetySettings) -> SafetySettings:
    """SafetySettings pour la variante Science.

    Le poids scientifique est amplifié ; les interdictions restent absolues.
    """
    return _apply_factors(base, _SCIENCE_FACTORS)
