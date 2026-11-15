"""Règles et anti-rebond du moteur d'alertes (A3)."""

from __future__ import annotations

from datetime import UTC, datetime

from marswalk_api.services.a3.clock import Stamp
from marswalk_api.services.a3.engine import AlertEngine
from marswalk_api.services.a3.rules import (
    DOSE_RATE_DANGER_USV_H,
    EvaReading,
    condition_findings,
    eva_findings,
)
from marswalk_core.config import load_safety_settings
from marswalk_core.schemas import AlertCause, AlertLevel, Conditions, SpaceWeather

S = load_safety_settings()
ST = Stamp(datetime(2026, 11, 14, tzinfo=UTC), 14, "13:00:00", 13.0)


def dose(rate: float) -> list:  # type: ignore[type-arg]
    c = Conditions(utc=ST.utc, dose_rate_usv_h=rate, dust_tau=0.5, space_weather=SpaceWeather())
    return [f for f in condition_findings(c, S) if f.cause == AlertCause.radiation]


def test_three_levels_with_advised_action() -> None:
    assert dose(10)[0].level is None
    caution = dose(35)[0]
    assert caution.level == AlertLevel.caution and caution.action
    danger = dose(250)[0]
    assert danger.level == AlertLevel.danger
    assert danger.action == "Retour à l'abri"
    assert danger.threshold == DOSE_RATE_DANGER_USV_H and danger.unit == "µSv/h"


def test_eva_rules_use_safety_yaml() -> None:
    r = EvaReading(reserve_pct=S.min_reserve_pct - 1, slope_deg=S.max_slope_deg + 1, radio=0.0)
    found = {f.cause: f for f in eva_findings(r, S)}
    assert found[AlertCause.return_reserve].level == AlertLevel.danger
    assert found[AlertCause.slope].level == AlertLevel.danger
    assert found[AlertCause.radio].level == AlertLevel.caution
    assert found[AlertCause.return_reserve].action == "Retour immédiat vers l'habitat"


def test_danger_is_immediate_caution_waits() -> None:
    e = AlertEngine(raise_after_s=2, clear_after_s=5)
    assert e.process(None, dose(35), 0.0, ST).raised == []
    assert e.process(None, dose(35), 1.0, ST).raised == []
    raised = e.process(None, dose(35), 2.0, ST).raised
    assert [a.level for a in raised] == [AlertLevel.caution]
    up = e.process(None, dose(250), 2.1, ST)
    assert [a.level for a in up.raised] == [AlertLevel.danger]
    assert up.cleared[0][0].id == raised[0].id


def test_no_flicker_around_threshold() -> None:
    """Une valeur qui oscille autour du seuil ne lève et ne lève qu'une alerte."""
    e = AlertEngine(raise_after_s=2, clear_after_s=5)
    raised, cleared = 0, 0
    for i in range(200):
        rate = DOSE_RATE_DANGER_USV_H + (1.0 if i % 2 else -1.0)
        ch = e.process(None, dose(rate), i * 0.2, ST)
        raised += len(ch.raised)
        cleared += len(ch.cleared)
    assert raised == 1 and cleared == 0
    assert len(e.list()) == 1


def test_clear_after_calm_period() -> None:
    e = AlertEngine(raise_after_s=2, clear_after_s=5)
    alert = e.process(None, dose(250), 0.0, ST).raised[0]
    assert e.process(None, dose(10), 1.0, ST).cleared == []
    assert e.process(None, dose(10), 5.0, ST).cleared == []
    cleared = e.process(None, dose(10), 6.0, ST).cleared
    assert [a.id for a, _ in cleared] == [alert.id]
    assert e.list() == [] and len(e.list(active=False)) == 1


def test_alerts_sorted_by_severity_and_carry_time() -> None:
    e = AlertEngine(raise_after_s=0, clear_after_s=5)
    e.process("eva-1", eva_findings(EvaReading(slope_deg=S.penalty_slope_deg + 1), S), 0.0, ST)
    e.process(None, dose(250), 0.0, ST)
    alerts = e.list("eva-1")
    assert [a.level for a in alerts] == [AlertLevel.danger, AlertLevel.caution]
    assert all((a.utc, a.sol, a.lmst) == (ST.utc, ST.sol, ST.lmst) for a in alerts)
