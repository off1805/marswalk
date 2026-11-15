"""Règles d'alerte (A3, EF-08) : comparaison des mesures aux seuils de ``safety.yaml``.

Chaque règle rend un ``Finding`` : le niveau atteint (``None`` si tout va bien), la valeur,
le seuil franchi et l'action conseillée. Le niveau est calculé deux fois : au seuil strict,
pour lever une alerte, et avec une marge d'hystérésis, pour la garder tant que la valeur
n'est pas nettement redescendue (anti-rebond, voir ``engine.py``).

Les seuils qui ne figurent pas dans ``safety.yaml`` (débit de dose, lumière restante, temps
avant le point de non-retour) sont des hypothèses de conception, réunies ci-dessous.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from marswalk_core.schemas import (
    AlertCause,
    AlertLevel,
    Conditions,
    SafetySettings,
    SpaceWeatherLevel,
)

# Hypothèses (à justifier par S1 et I1) ---------------------------------------
DOSE_RATE_CAUTION_USV_H = 30.0
"""Environ trois fois le fond mesuré au sol par RAD (de l'ordre de 10 µSv/h)."""
DOSE_RATE_DANGER_USV_H = 50.0
"""Au-delà : événement à particules solaires, abri nécessaire."""
DOSE_CAUTION_FRACTION = 0.8
"""Vigilance à 80 % de la dose maximale de la sortie."""
DUST_CAUTION_FRACTION = 0.8
RESERVE_CAUTION_MARGIN_PCT = 10.0
"""Vigilance quand la réserve au retour approche du minimum de 10 points."""
PNR_CAUTION_S = 900.0
"""Vigilance à 15 min du point de non-retour."""
DAYLIGHT_CAUTION_S = 3700.0
"""Environ une heure martienne avant le coucher du Soleil."""
DAYLIGHT_DANGER_S = 1850.0
HYSTERESIS = 0.05
"""Une alerte reste active tant que la valeur n'est pas 5 % sous son seuil."""


@dataclass(frozen=True)
class Finding:
    cause: AlertCause
    level: AlertLevel | None
    """Niveau au seuil strict : sert à lever une alerte."""
    held_level: AlertLevel | None
    """Niveau avec la marge d'hystérésis : sert à garder une alerte déjà levée."""
    value: float | None = None
    threshold: float | None = None
    unit: str | None = None
    title: str = ""
    message: str = ""
    action: str = ""


Texts = dict[AlertLevel, tuple[str, str, str]]
"""Par niveau : titre, message (avec ``{value}`` et ``{threshold}``), action conseillée."""


def _above(
    cause: AlertCause,
    value: float | None,
    caution: float,
    danger: float,
    unit: str,
    texts: Texts,
) -> Finding:
    """Règle « plus c'est haut, plus c'est grave »."""
    return _rule(cause, value, caution, danger, unit, texts, lambda v, t: v >= t, 1 - HYSTERESIS)


def _below(
    cause: AlertCause,
    value: float | None,
    caution: float,
    danger: float,
    unit: str,
    texts: Texts,
) -> Finding:
    """Règle « plus c'est bas, plus c'est grave »."""
    return _rule(cause, value, caution, danger, unit, texts, lambda v, t: v <= t, 1 + HYSTERESIS)


def _rule(
    cause: AlertCause,
    value: float | None,
    caution: float,
    danger: float,
    unit: str,
    texts: Texts,
    crosses: Callable[[float, float], bool],
    margin: float,
) -> Finding:
    if value is None:
        return Finding(cause, None, None)

    def level_at(scale: float) -> AlertLevel | None:
        if crosses(value, _scaled(danger, scale)):
            return AlertLevel.danger
        if crosses(value, _scaled(caution, scale)):
            return AlertLevel.caution
        return None

    level, held = level_at(1.0), level_at(margin)
    shown = level or held
    if shown is None:
        return Finding(cause, None, None, value=value, unit=unit)
    threshold = danger if shown == AlertLevel.danger else caution
    title, message, action = texts[shown]
    return Finding(
        cause,
        level,
        held,
        value=round(value, 2),
        threshold=threshold,
        unit=unit,
        title=title,
        message=message.format(value=_fmt(value), threshold=_fmt(threshold), unit=unit),
        action=action,
    )


def _scaled(threshold: float, scale: float) -> float:
    """Applique la marge ; un seuil nul reçoit une marge absolue."""
    if threshold == 0:
        return (scale - 1) * 60.0
    return threshold * scale


def _fmt(v: float) -> str:
    return f"{v:.0f}" if abs(v) >= 10 else f"{v:.1f}"


# Règles sur les conditions ---------------------------------------------------


def condition_findings(c: Conditions, s: SafetySettings) -> list[Finding]:
    """Débit de dose, météo spatiale et opacité de l'atmosphère."""
    out = [
        _above(
            AlertCause.radiation,
            c.dose_rate_usv_h,
            DOSE_RATE_CAUTION_USV_H,
            DOSE_RATE_DANGER_USV_H,
            "µSv/h",
            {
                AlertLevel.caution: (
                    "Débit de dose en hausse",
                    "Débit de dose de {value} {unit} (vigilance à {threshold}).",
                    "Préparer le retour",
                ),
                AlertLevel.danger: (
                    "Événement à particules solaires",
                    "Débit de dose de {value} {unit}, au-delà de {threshold}. Abri nécessaire.",
                    "Retour à l'abri",
                ),
            },
        ),
        _above(
            AlertCause.dust,
            c.dust_tau,
            s.max_dust_tau * DUST_CAUTION_FRACTION,
            s.max_dust_tau,
            "τ",
            {
                AlertLevel.caution: (
                    "Atmosphère chargée de poussière",
                    "Opacité de {value} (vigilance à {threshold}).",
                    "Surveiller la visibilité",
                ),
                AlertLevel.danger: (
                    "Tempête de poussière",
                    "Opacité de {value}, au-delà de {threshold}.",
                    "Retour vers l'habitat",
                ),
            },
        ),
    ]
    sw = c.space_weather.level
    sw_level = {
        SpaceWeatherLevel.watch: AlertLevel.info,
        SpaceWeatherLevel.warning: AlertLevel.caution,
        SpaceWeatherLevel.storm: AlertLevel.danger,
    }.get(sw)
    if sw_level is not None:
        event = c.space_weather.event or "activité solaire"
        texts = {
            AlertLevel.info: ("Météo spatiale à surveiller", f"{event}.", "Rester informé"),
            AlertLevel.caution: (
                "Alerte de météo spatiale",
                f"{event} : arrivée de particules possible.",
                "Préparer le retour à l'abri",
            ),
            AlertLevel.danger: (
                "Tempête solaire",
                f"{event} : particules énergétiques attendues.",
                "Retour à l'abri",
            ),
        }
        title, message, action = texts[sw_level]
        out.append(
            Finding(
                AlertCause.solar_event,
                sw_level,
                sw_level,
                title=title,
                message=message,
                action=action,
            )
        )
    else:
        out.append(Finding(AlertCause.solar_event, None, None))
    return out


# Règles sur la télémétrie d'une sortie -------------------------------------------


@dataclass(frozen=True)
class EvaReading:
    """Ce que A3 sait d'une sortie à un instant : télémétrie, budgets et terrain."""

    dose_usv: float | None = None
    oxygen_pct: float | None = None
    battery_pct: float | None = None
    reserve_pct: float | None = None
    time_to_pnr_s: float | None = None
    slope_deg: float | None = None
    radio: float | None = None
    """1 couvert, 0 hors couverture."""
    illumination: float | None = None
    daylight_left_s: float | None = None


def eva_findings(r: EvaReading, s: SafetySettings) -> list[Finding]:
    out = [
        _above(
            AlertCause.radiation,
            r.dose_usv,
            s.max_dose_usv * DOSE_CAUTION_FRACTION,
            s.max_dose_usv,
            "µSv",
            {
                AlertLevel.caution: (
                    "Dose cumulée élevée",
                    "Dose de la sortie : {value} {unit} (vigilance à {threshold}).",
                    "Écourter la sortie",
                ),
                AlertLevel.danger: (
                    "Dose maximale atteinte",
                    "Dose de la sortie : {value} {unit}, limite {threshold}.",
                    "Retour à l'abri",
                ),
            },
        ),
        _below(
            AlertCause.return_reserve,
            r.reserve_pct,
            s.min_reserve_pct + RESERVE_CAUTION_MARGIN_PCT,
            s.min_reserve_pct,
            "%",
            {
                AlertLevel.caution: (
                    "Réserve au retour en baisse",
                    "Réserve prévue au retour : {value} % (minimum {threshold} %).",
                    "Renoncer à la prochaine cible",
                ),
                AlertLevel.danger: (
                    "Réserve au retour insuffisante",
                    "Réserve prévue au retour : {value} %, sous le minimum de {threshold} %.",
                    "Retour immédiat vers l'habitat",
                ),
            },
        ),
        _below(
            AlertCause.point_of_no_return,
            r.time_to_pnr_s,
            PNR_CAUTION_S,
            0.0,
            "s",
            {
                AlertLevel.caution: (
                    "Point de non-retour proche",
                    "Point de non-retour dans {value} s.",
                    "Préparer le demi-tour",
                ),
                AlertLevel.danger: (
                    "Point de non-retour dépassé",
                    "Le point de non-retour est dépassé.",
                    "Retour immédiat vers l'habitat",
                ),
            },
        ),
        _below(
            AlertCause.consumables,
            _min(r.oxygen_pct, r.battery_pct),
            s.min_reserve_pct + RESERVE_CAUTION_MARGIN_PCT,
            s.min_reserve_pct,
            "%",
            {
                AlertLevel.caution: (
                    "Consommables en baisse",
                    "Oxygène ou batterie à {value} %.",
                    "Préparer le retour",
                ),
                AlertLevel.danger: (
                    "Consommables bas",
                    "Oxygène ou batterie à {value} %, sous {threshold} %.",
                    "Retour immédiat vers l'habitat",
                ),
            },
        ),
        _above(
            AlertCause.slope,
            r.slope_deg,
            s.penalty_slope_deg,
            s.max_slope_deg,
            "°",
            {
                AlertLevel.caution: ("Pente soutenue", "Pente de {value}° ici.", "Ralentir"),
                AlertLevel.danger: (
                    "Pente trop forte",
                    "Pente de {value}°, au-delà de {threshold}°.",
                    "Reculer et contourner",
                ),
            },
        ),
        _below(
            AlertCause.illumination,
            r.daylight_left_s,
            DAYLIGHT_CAUTION_S,
            DAYLIGHT_DANGER_S,
            "s",
            {
                AlertLevel.caution: (
                    "Fin de journée proche",
                    "Coucher du Soleil dans {value} s.",
                    "Planifier le retour",
                ),
                AlertLevel.danger: (
                    "Lumière insuffisante bientôt",
                    "Coucher du Soleil dans {value} s.",
                    "Retour vers l'habitat",
                ),
            },
        ),
    ]
    if r.radio is not None and r.radio < 0.5:
        level = AlertLevel.danger if s.require_radio else AlertLevel.caution
        out.append(
            Finding(
                AlertCause.radio,
                level,
                level,
                value=r.radio,
                unit=None,
                title="Hors couverture radio",
                message="La position n'est pas visible depuis l'antenne de l'habitat.",
                action="Rejoindre une zone couverte",
            )
        )
    else:
        out.append(Finding(AlertCause.radio, None, None))
    return out


def _min(*values: float | None) -> float | None:
    known = [v for v in values if v is not None]
    return min(known) if known else None
