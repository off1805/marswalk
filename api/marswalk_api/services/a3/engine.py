"""Moteur d'alertes (A3) : niveaux, anti-rebond, acquittement.

Une alerte est suivie par couple (sortie, cause). Anti-rebond :

- une alerte ``danger`` est levée dès la première mesure ;
- une alerte ``caution`` ou ``info`` l'est si la condition dure ``raise_after_s`` ;
- une alerte levée reste active tant que la valeur n'est pas repassée sous le seuil diminué
  de la marge d'hystérésis (``Finding.held_level``), puis pendant ``clear_after_s`` ;
- un passage à un niveau plus grave remplace l'alerte aussitôt ; un retour à un niveau moins
  grave attend ``clear_after_s``.

Acquitter une alerte la garde active (la condition dure) mais la sort du bandeau à traiter.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, field

from marswalk_core.schemas import Alert, AlertCause, AlertLevel, LonLat

from .clock import Stamp
from .rules import Finding

SEVERITY = {AlertLevel.info: 0, AlertLevel.caution: 1, AlertLevel.danger: 2}


@dataclass
class _Track:
    alert_id: str | None = None
    level: AlertLevel | None = None
    pending_level: AlertLevel | None = None
    pending_since: float | None = None
    ok_since: float | None = None


@dataclass
class Change:
    raised: list[Alert] = field(default_factory=list)
    cleared: list[tuple[Alert, str]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.raised or self.cleared)


class AlertEngine:
    def __init__(self, raise_after_s: float = 2.0, clear_after_s: float = 5.0) -> None:
        self.raise_after_s = raise_after_s
        self.clear_after_s = clear_after_s
        self._alerts: dict[str, Alert] = {}
        self._active: set[str] = set()
        self._tracks: dict[tuple[str | None, AlertCause], _Track] = {}
        self._ids = itertools.count(1)

    # -- lecture ---------------------------------------------------------------
    def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    def is_active(self, alert_id: str) -> bool:
        return alert_id in self._active

    def list(self, eva_id: str | None = None, active: bool = True) -> list[Alert]:
        """Alertes, les plus graves puis les plus récentes en tête (hiérarchie, ENF-08).

        Avec ``eva_id``, les alertes de cette sortie et celles du site (conditions).
        """
        out = [
            a
            for a in self._alerts.values()
            if (not active or a.id in self._active)
            and (eva_id is None or a.eva_id in (None, eva_id))
        ]
        return sorted(out, key=lambda a: (-SEVERITY[a.level], a.acknowledged, -a.utc.timestamp()))

    # -- acquittement ----------------------------------------------------------
    def acknowledge(self, alert_id: str, stamp: Stamp) -> Alert | None:
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None
        if not alert.acknowledged:
            alert = alert.model_copy(update={"acknowledged": True, "acknowledged_at": stamp.utc})
            self._alerts[alert_id] = alert
        return alert

    # -- évaluation ------------------------------------------------------------
    def process(
        self,
        eva_id: str | None,
        findings: Iterable[Finding],
        now: float,
        stamp: Stamp,
        position: LonLat | None = None,
    ) -> Change:
        """Met à jour les alertes de ``eva_id`` (``None`` : site) ; ``now`` en secondes."""
        change = Change()
        for f in findings:
            track = self._tracks.setdefault((eva_id, f.cause), _Track())
            self._step(track, f, eva_id, now, stamp, position, change)
        return change

    def _step(
        self,
        t: _Track,
        f: Finding,
        eva_id: str | None,
        now: float,
        stamp: Stamp,
        position: LonLat | None,
        change: Change,
    ) -> None:
        wanted = f.held_level if t.level is not None else f.level
        if t.level is not None and f.level is not None and _worse(f.level, t.level):
            wanted = f.level

        if wanted is None or (t.level is not None and _worse(t.level, wanted)):
            # Retour au calme, ou à un niveau moins grave : attendre clear_after_s.
            t.pending_level, t.pending_since = None, None
            if t.level is None:
                return
            t.ok_since = t.ok_since if t.ok_since is not None else now
            if now - t.ok_since < self.clear_after_s:
                return
            self._clear(t, change, "condition revenue sous le seuil")
            if wanted is None:
                return
            # Niveau moins grave encore atteint : il est levé tout de suite.
            self._raise(t, f, wanted, eva_id, stamp, position, change)
            return

        t.ok_since = None
        if t.level == wanted:
            return
        immediate = wanted == AlertLevel.danger or t.level is not None
        if not immediate:
            if t.pending_level != wanted:
                t.pending_level, t.pending_since = wanted, now
            assert t.pending_since is not None
            if now - t.pending_since < self.raise_after_s:
                return
        if t.level is not None:
            self._clear(t, change, "niveau relevé")
        self._raise(t, f, wanted, eva_id, stamp, position, change)

    def _raise(
        self,
        t: _Track,
        f: Finding,
        level: AlertLevel,
        eva_id: str | None,
        stamp: Stamp,
        position: LonLat | None,
        change: Change,
    ) -> None:
        alert = Alert(
            id=f"alert-{next(self._ids)}",
            eva_id=eva_id,
            level=level,
            cause=f.cause,
            title=f.title,
            message=f.message,
            action=f.action,
            value=f.value,
            threshold=f.threshold,
            unit=f.unit,
            position=position,
            utc=stamp.utc,
            sol=stamp.sol,
            lmst=stamp.lmst,
        )
        self._alerts[alert.id] = alert
        self._active.add(alert.id)
        t.alert_id, t.level = alert.id, level
        t.pending_level = t.pending_since = t.ok_since = None
        change.raised.append(alert)

    def _clear(self, t: _Track, change: Change, reason: str) -> None:
        if t.alert_id is not None:
            self._active.discard(t.alert_id)
            change.cleared.append((self._alerts[t.alert_id], reason))
        t.alert_id, t.level, t.ok_since = None, None, None

    def clear_scope(self, eva_id: str | None, reason: str) -> Change:
        """Lève toutes les alertes actives de ``eva_id`` (``None`` : site) sans attendre.

        Sert quand la source des mesures change (fin d'un scénario de conditions) : les
        alertes levées par l'ancienne source ne décrivent plus rien.
        """
        change = Change()
        for (scope, _cause), t in self._tracks.items():
            if scope == eva_id:
                if t.alert_id is not None:
                    self._clear(t, change, reason)
                t.pending_level = t.pending_since = t.ok_since = None
        return change

    def reset(self) -> None:
        self._alerts.clear()
        self._active.clear()
        self._tracks.clear()


def _worse(a: AlertLevel, b: AlertLevel) -> bool:
    return SEVERITY[a] > SEVERITY[b]
