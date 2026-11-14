"""Modèles SQLAlchemy, alignés sur la migration ``0001_initial`` (gelés avec contrats-v1).

Les géométries sont en SRID 949900, Mars 2000 géographique (IAU_2015:49900), en degrés.
Les structures riches (segments, profil, réglages) sont stockées en JSONB, sérialisées
depuis les modèles Pydantic de ``marswalk_core.schemas``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from marswalk_core.schemas import POSTGIS_MARS_SRID

SRID = POSTGIS_MARS_SRID


def point() -> Any:
    return Geometry("POINT", srid=SRID, spatial_index=False)  # index GiST créés par la migration


class Base(DeclarativeBase):
    pass


class SiteSettingsRow(Base):
    __tablename__ = "site_settings"
    site_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TargetRow(Base):
    __tablename__ = "targets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    objective: Mapped[str | None] = mapped_column(Text)
    measurement: Mapped[str | None] = mapped_column(Text)
    work_time_s: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer)
    geom: Mapped[Any] = mapped_column(point())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanRow(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departure_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_geom: Mapped[Any] = mapped_column(point())
    return_geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=SRID, spatial_index=False))
    target_ids: Mapped[list[str]] = mapped_column(JSONB)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    suit: Mapped[dict[str, Any]] = mapped_column(JSONB)
    selected_route_id: Mapped[str | None] = mapped_column(String(64))
    compute_time_ms: Mapped[float | None] = mapped_column(Float)


class RouteRow(Base):
    __tablename__ = "routes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    variant: Mapped[str] = mapped_column(String(16))
    geom: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=SRID, spatial_index=False))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """segments, profile, totals, return_check, explanation, warnings"""


class EvaRow(Base):
    __tablename__ = "evas"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    crew: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geom: Mapped[Any] = mapped_column(point())
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """cap, vitesse, consommables, dose, distance, budgets (schéma Eva)"""


class ObservationRow(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    eva_id: Mapped[str] = mapped_column(ForeignKey("evas.id", ondelete="CASCADE"), index=True)
    utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sol: Mapped[int] = mapped_column(Integer)
    lmst: Mapped[str] = mapped_column(String(8))
    note: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(String(64))
    geom: Mapped[Any] = mapped_column(point())


class ObstacleRow(Base):
    __tablename__ = "obstacles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    eva_id: Mapped[str] = mapped_column(ForeignKey("evas.id", ondelete="CASCADE"), index=True)
    utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    radius_m: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[Any] = mapped_column(point())


class AlertRow(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    eva_id: Mapped[str | None] = mapped_column(
        ForeignKey("evas.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16))
    cause: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    geom: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=SRID, spatial_index=False))
    utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sol: Mapped[int] = mapped_column(Integer)
    lmst: Mapped[str] = mapped_column(String(8))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
