"""Budgets et retour garanti (P3). BOUCHON de T00 : consommation constante.

Signature gelée : ``return_check(estimate, return_field, suit) -> ReturnCheck``.
"""

from __future__ import annotations

from marswalk_core.grids import ReturnField, RouteEstimate
from marswalk_core.schemas import ReturnCheck, ReturnStatus, SuitModel

MIN_RESERVE_PCT = 30.0


def return_check(estimate: RouteEstimate, return_field: ReturnField, suit: SuitModel) -> ReturnCheck:
    oxygen = sum(s.oxygen_kg for s in estimate.segments)
    reserve = 100.0 * (1.0 - oxygen / suit.oxygen_capacity_kg)
    if reserve >= MIN_RESERVE_PCT + 10:
        status = ReturnStatus.ok
    elif reserve >= MIN_RESERVE_PCT:
        status = ReturnStatus.marginal
    else:
        status = ReturnStatus.fail
    return ReturnCheck(
        status=status,
        reserve_at_return_pct=round(reserve, 1),
        limiting_consumable="oxygen",
        point_of_no_return=None,
        point_of_no_return_time_s=None,
        targets_to_cut=[],
        message="bouchon T00 : consommation constante, point de non-retour non calculé",
    )
