"""Migration initiale sur PostGIS (marqueur db : demande MARSWALK_DATABASE_URL)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

URL = os.environ.get("MARSWALK_DATABASE_URL")
pytestmark = [pytest.mark.db, pytest.mark.skipif(not URL, reason="MARSWALK_DATABASE_URL absent")]

TABLES = {
    "site_settings",
    "targets",
    "plans",
    "routes",
    "evas",
    "observations",
    "obstacles",
    "alerts",
}


def test_upgrade_creates_tables_and_mars_srid() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(cfg, "base") if _has_version() else None
    command.upgrade(cfg, "head")
    engine = create_engine(URL or "")
    assert set(inspect(engine).get_table_names()) >= TABLES
    with engine.connect() as conn:
        srid = conn.execute(
            text("SELECT auth_name, auth_srid FROM spatial_ref_sys WHERE srid = 949900")
        )
        assert srid.one() == ("IAU_2015", 49900)
        conn.execute(
            text(
                "INSERT INTO targets VALUES ('t', 'fictif', 'n', 'science', NULL, NULL, 60, 2, "
                "ST_SetSRID(ST_MakePoint(77.58, 18.38), 949900), now(), now())"
            )
        )
        dist = conn.execute(
            text("SELECT ST_Distance(geom::geography, geom::geography) FROM targets WHERE id = 't'")
        )
        assert dist is not None
        conn.rollback()


def _has_version() -> bool:
    engine = create_engine(URL or "")
    return "alembic_version" in inspect(engine).get_table_names()
