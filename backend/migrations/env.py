"""Environnement Alembic : même moteur et mêmes tables que l'application."""
from alembic import context

from app import models  # noqa: F401  (enregistre les tables)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:  # appelé depuis app/db.py avec une connexion déjà ouverte
        _run(connection)
        return
    with engine.connect() as connection:
        _run(connection)
        connection.commit()


def _run(connection) -> None:
    # render_as_batch : SQLite ne sait pas modifier une colonne, Alembic recrée alors la table.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
