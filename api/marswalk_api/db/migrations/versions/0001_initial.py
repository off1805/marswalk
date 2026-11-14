"""Migration initiale complète (T00, gelée avec contrats-v1).

Crée PostGIS, le SRID 949900 (Mars 2000 géographique, IAU_2015:49900) et les tables
site_settings, targets, plans, routes, evas, observations, obstacles et alerts.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SRID = 949900
MARS_2000_WKT = (
    'GEOGCS["Mars 2000",DATUM["D_Mars_2000",SPHEROID["Mars_2000_IAU_IAG",3396190,0]],'
    'PRIMEM["Reference_Meridian",0],UNIT["Degree",0.0174532925199433]]'
)


def _point() -> Geometry:
    return Geometry("POINT", srid=SRID, spatial_index=False)


def _tz() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        sa.text(
            "INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) "
            "VALUES (:srid, 'IAU_2015', 49900, '+proj=longlat +R=3396190 +no_defs +type=crs', :wkt) "
            "ON CONFLICT (srid) DO NOTHING"
        ).bindparams(srid=SRID, wkt=MARS_2000_WKT)
    )

    op.create_table(
        "site_settings",
        sa.Column("site_id", sa.String(64), primary_key=True),
        sa.Column("settings", JSONB, nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
    )
    op.create_table(
        "targets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("objective", sa.Text),
        sa.Column("measurement", sa.Text),
        sa.Column("work_time_s", sa.Float, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("geom", _point(), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("updated_at", _tz(), nullable=False),
    )
    op.create_table(
        "plans",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.Text),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", _tz(), nullable=False),
        sa.Column("departure_utc", _tz()),
        sa.Column("start_geom", _point(), nullable=False),
        sa.Column("return_geom", _point(), nullable=False),
        sa.Column("target_ids", JSONB, nullable=False),
        sa.Column("settings", JSONB, nullable=False),
        sa.Column("suit", JSONB, nullable=False),
        sa.Column("selected_route_id", sa.String(64)),
        sa.Column("compute_time_ms", sa.Float),
    )
    op.create_table(
        "routes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "plan_id", sa.String(64), sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("variant", sa.String(16), nullable=False),
        sa.Column("geom", Geometry("LINESTRING", srid=SRID, spatial_index=False), nullable=False),
        sa.Column("data", JSONB, nullable=False),
    )
    op.create_table(
        "evas",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("site_id", sa.String(64), nullable=False, index=True),
        sa.Column(
            "plan_id", sa.String(64), sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "route_id", sa.String(64), sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("crew", JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", _tz()),
        sa.Column("ended_at", _tz()),
        sa.Column("geom", _point(), nullable=False),
        sa.Column("state", JSONB, nullable=False),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "eva_id", sa.String(64), sa.ForeignKey("evas.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("utc", _tz(), nullable=False),
        sa.Column("sol", sa.Integer, nullable=False),
        sa.Column("lmst", sa.String(8), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("photo_url", sa.Text),
        sa.Column("target_id", sa.String(64)),
        sa.Column("geom", _point(), nullable=False),
    )
    op.create_table(
        "obstacles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "eva_id", sa.String(64), sa.ForeignKey("evas.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("utc", _tz(), nullable=False),
        sa.Column("radius_m", sa.Float, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("geom", _point(), nullable=False),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "eva_id", sa.String(64), sa.ForeignKey("evas.id", ondelete="CASCADE"), index=True
        ),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("cause", sa.String(32), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("threshold", sa.Float),
        sa.Column("unit", sa.String(32)),
        sa.Column("geom", _point()),
        sa.Column("utc", _tz(), nullable=False, index=True),
        sa.Column("sol", sa.Integer, nullable=False),
        sa.Column("lmst", sa.String(8), nullable=False),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("acknowledged_at", _tz()),
    )
    for table, column in (
        ("targets", "geom"),
        ("plans", "start_geom"),
        ("routes", "geom"),
        ("evas", "geom"),
        ("observations", "geom"),
        ("obstacles", "geom"),
    ):
        op.create_index(f"ix_{table}_{column}_gist", table, [column], postgresql_using="gist")


def downgrade() -> None:
    for table in ("alerts", "obstacles", "observations", "evas", "routes", "plans", "targets",
                  "site_settings"):
        op.drop_table(table)
    op.execute(sa.text("DELETE FROM spatial_ref_sys WHERE srid = :srid").bindparams(srid=SRID))
