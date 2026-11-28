from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

def _normalize(url: str) -> str:
    """Accepte le lien tel que Railway ou Render le donnent (postgres:// ou postgresql://)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _normalize(settings.database_url)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=not DATABASE_URL.startswith("sqlite"))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Met la base au niveau des migrations Alembic (dossier migrations/).

    Une base créée avant Alembic (tables présentes, pas de table alembic_version) reçoit d'abord
    les colonnes manquantes puis est marquée au niveau actuel, sans perdre de données."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from . import models  # noqa: F401  (enregistre les tables)

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    insp = inspect(engine)
    legacy = insp.has_table("users") and not insp.has_table("alembic_version")
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        if legacy:
            Base.metadata.create_all(bind=conn)
            _add_missing_columns(conn)
            _legacy_fixes(conn)
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")


def _add_missing_columns(conn) -> None:
    """Reprise d'une base d'avant Alembic : ajoute les colonnes apparues depuis sa création
    (create_all ne crée que les tables manquantes). Les évolutions suivantes passent par Alembic."""
    import json

    from sqlalchemy import inspect, text

    insp = inspect(conn)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            ddl_type = col.type.compile(dialect=engine.dialect)
            default = ""
            if col.default is not None and getattr(col.default, "is_scalar", False):
                v = col.default.arg
                if isinstance(v, bool):
                    default = f" DEFAULT {'TRUE' if v else 'FALSE'}" if engine.dialect.name != "sqlite" else f" DEFAULT {int(v)}"
                elif isinstance(v, (int, float)):
                    default = f" DEFAULT {v}"
                elif isinstance(v, str):
                    default = " DEFAULT '" + v.replace("'", "''") + "'"
            elif col.default is not None and getattr(col.default, "is_callable", False):
                try:
                    v = col.default.arg(None)
                except Exception:  # noqa: BLE001 - ex. utcnow : pas de valeur par défaut en SQL
                    v = None
                if isinstance(v, (list, dict)):
                    default = " DEFAULT '" + json.dumps(v) + "'"
            conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {ddl_type}{default}'))


def _legacy_fixes(conn) -> None:
    """Reprise d'une base créée sans Alembic par une ancienne version du site (create_all) :
    - l'ancienne colonne booléenne users.email_verified devient la date email_verified_at (les adresses
      déjà confirmées le restent), puis elle est supprimée (elle bloquerait la création des comptes) ;
    - les index déclarés dans les modèles sont créés s'ils manquent."""
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if insp.has_table("users"):
        columns = {c["name"] for c in insp.get_columns("users")}
        if "email_verified" in columns:
            true = "1" if engine.dialect.name == "sqlite" else "TRUE"
            conn.execute(text("UPDATE users SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                              f"WHERE email_verified_at IS NULL AND email_verified = {true}"))
            conn.execute(text("ALTER TABLE users DROP COLUMN email_verified"))
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(conn, checkfirst=True)
