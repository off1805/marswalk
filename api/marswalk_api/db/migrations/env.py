"""Environnement Alembic. Aucune tâche autre que T00 n'ajoute de migration (contrats-v1)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from marswalk_api.db.models import Base

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("MARSWALK_DATABASE_URL")
    if not url:
        raise RuntimeError("MARSWALK_DATABASE_URL n'est pas défini")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
