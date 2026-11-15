"""Budgets et retour garanti (P3).

Vérification du consommable limitant, point de non-retour et liste des cibles
à couper si la réserve minimale n'est pas garantie.

Signature gelée : ``return_check(estimate, return_field, suit) -> ReturnCheck``.

Sources : see docs/science/hypotheses-marche.md §7.
"""

from __future__ import annotations

import math
from typing import Literal

from marswalk_core.grids import ReturnField, RouteEstimate
from marswalk_core.schemas import LonLat, ReturnCheck, ReturnStatus, SuitModel

Consumable = Literal["oxygen", "battery", "water"]

MIN_RESERVE_PCT: float = 30.0  # réserve minimale garantie, en %


def _capacity(suit: SuitModel, consumable: Consumable) -> float:
    """Capacité totale du consommable (en unité native)."""
    if consumable == "oxygen":
        return suit.oxygen_capacity_kg
    if consumable == "battery":
        return suit.battery_capacity_wh
    if consumable == "water":
        return suit.water_capacity_l
    raise ValueError(f"Consommable inconnu : {consumable}")


def _used(estimate: RouteEstimate, consumable: Consumable) -> float:
    """Total consommé sur tout l'itinéraire."""
    if consumable == "oxygen":
        return sum(s.oxygen_kg for s in estimate.segments)
    if consumable == "battery":
        return sum(s.battery_wh for s in estimate.segments)
    if consumable == "water":
        return sum(s.water_l for s in estimate.segments)
    raise ValueError(f"Consommable inconnu : {consumable}")


def _reserve_pct(used: float, capacity: float) -> float:
    """Réserve en % : 100 × (1 - used/capacity). Peut être négative."""
    if capacity <= 0:
        return 0.0
    return 100.0 * (1.0 - used / capacity)


def _limiting_consumable(estimate: RouteEstimate, suit: SuitModel) -> tuple[Consumable, float]:
    """Renvoie (nom, réserve_pct) pour le consommable le plus contraint."""
    best_reserve = 100.0
    best_name: Consumable = "oxygen"
    consumables: list[Consumable] = ["oxygen", "battery", "water"]
    for c_name in consumables:
        u = _used(estimate, c_name)
        cap = _capacity(suit, c_name)
        r = _reserve_pct(u, cap)
        if r < best_reserve:
            best_reserve = r
            best_name = c_name
    return best_name, best_reserve


def _return_cost_at_sample_index(
    estimate: RouteEstimate, sample_idx: int, field: ReturnField
) -> float:
    """Temps de retour depuis la position d'un échantillon de profil, ou inf si inconnu."""
    pos = estimate.samples_position[sample_idx]
    from marswalk_core.geodesy import to_analysis as _ta

    x, y = _ta(field.site, pos.lon, pos.lat)
    cell = field.site.xy_to_cell(x, y)
    if cell is None:
        return math.inf
    val = float(field.seconds[cell])
    return val


def return_check(
    estimate: RouteEstimate, return_field: ReturnField, suit: SuitModel
) -> ReturnCheck:
    """Vérifie la réserve de retour avec 30 % de marge.

    Calcule le consommable limitant, la réserve au retour, le point de
    non-retour et la liste des cibles à couper si la réserve est insuffisante.

    Le point de non-retour (PNR) est le dernier échantillon du profil à partir
    duquel on peut encore rentrer en ayant 30 % de réserve sur le consommable
    limitant. Il est exprimé en position et en temps depuis le départ.
    """
    limiting_name, reserve_at_end = _limiting_consumable(estimate, suit)
    capacity = _capacity(suit, limiting_name)

    if reserve_at_end >= MIN_RESERVE_PCT + 10:
        status = ReturnStatus.ok
    elif reserve_at_end >= MIN_RESERVE_PCT:
        status = ReturnStatus.marginal
    else:
        status = ReturnStatus.fail

    # --- Point de non-retour (PNR) ---
    # On parcourt les échantillons du profil dans l'ordre croissant.
    # À chaque échantillon i :
    #   consommé_aller(i) = consommation des tronçons jusqu'à l'instant du profil
    #   retour(i) = temps de retour depuis la position[i]
    #   consommé_retour(i) ≈ retour(i) / durée_totale × consommé_total
    # Le PNR est le dernier i où consommé_aller(i) + consommé_retour(i) ≤ (1 - 30%) × capacity.

    n_samples = len(estimate.samples_time_s)
    pnr_pos: LonLat | None = None
    pnr_time: float | None = None

    if n_samples > 0:
        total_used = _used(estimate, limiting_name)
        budget = capacity * (1.0 - MIN_RESERVE_PCT / 100.0)  # ce que l'on peut dépenser

        # Consommation par seconde (approximation uniforme pour le retour)
        total_walk_t = sum(s.walk_time_s for s in estimate.segments)
        rate_per_s = total_used / total_walk_t if total_walk_t > 0 else 0.0

        for i in range(n_samples):
            t_here = estimate.samples_time_s[i]
            # Consommé à cet instant (proportionnel au temps de marche)
            used_here = rate_per_s * t_here
            # Coût du retour depuis cette position
            return_t = _return_cost_at_sample_index(estimate, i, return_field)
            if math.isinf(return_t):
                continue
            used_return = rate_per_s * return_t
            if used_here + used_return <= budget:
                # On peut encore rentrer : mettre à jour le PNR
                pnr_pos = estimate.samples_position[i]
                pnr_time = t_here

    # --- Cibles à couper si réserve insuffisante ---
    targets_to_cut: list[str] = []
    if status == ReturnStatus.fail:
        # Heuristique : couper les cibles du fond de la liste (les plus tardives en temps)
        # jusqu'à ce que la réserve simulée repasse au-dessus de 30 %.
        # Les tronçons sont : [h→t1, t1→t2, ..., tn→h].
        # Couper la cible tk (tronçon seg_i) réduit la consommation totale.
        # On ne connaît pas les IDs de cibles ici, on retourne les index de tronçon.
        remaining_used = _used(estimate, limiting_name)
        n_seg = len(estimate.segments)

        # Parcourir les tronçons aller (tous sauf le dernier qui est le retour),
        # en partant de la fin. Si n_seg == 1, le seul tronçon est le retour :
        # on le marque aussi pour signaler que l'itinéraire entier est trop long.
        candidates = list(range(max(0, n_seg - 2), -1, -1)) or [0]

        for seg_i in candidates:
            seg = estimate.segments[seg_i]
            if limiting_name == "oxygen":
                contrib = seg.oxygen_kg
            elif limiting_name == "battery":
                contrib = seg.battery_wh
            else:
                contrib = seg.water_l
            remaining_used = max(0.0, remaining_used - contrib)
            # Approx : on réduit aussi le tronçon retour associé de moitié
            if seg_i + 1 < n_seg:
                ret_seg = estimate.segments[seg_i + 1]
                if limiting_name == "oxygen":
                    remaining_used = max(0.0, remaining_used - ret_seg.oxygen_kg * 0.5)
                elif limiting_name == "battery":
                    remaining_used = max(0.0, remaining_used - ret_seg.battery_wh * 0.5)
                else:
                    remaining_used = max(0.0, remaining_used - ret_seg.water_l * 0.5)
            targets_to_cut.append(f"segment-{seg_i}")
            new_reserve = _reserve_pct(remaining_used, capacity)
            if new_reserve >= MIN_RESERVE_PCT:
                break

    return ReturnCheck(
        status=status,
        reserve_at_return_pct=round(reserve_at_end, 1),
        limiting_consumable=limiting_name,
        point_of_no_return=pnr_pos,
        point_of_no_return_time_s=round(pnr_time, 1) if pnr_time is not None else None,
        targets_to_cut=targets_to_cut,
        message=None,
    )
