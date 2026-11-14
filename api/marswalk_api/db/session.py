"""Moteur et sessions SQLAlchemy."""

from __future__ import annotations

from functools import cache
from typing import Literal

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@cache
def get_engine() -> Engine | None:
    from marswalk_api.deps import get_settings

    url = get_settings().database_url
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


@cache
def get_sessionmaker() -> sessionmaker[Session] | None:
    engine = get_engine()
    return None if engine is None else sessionmaker(engine, expire_on_commit=False)


def database_status() -> Literal["ok", "unavailable", "disabled"]:
    engine = get_engine()
    if engine is None:
        return "disabled"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return "unavailable"
    return "ok"
