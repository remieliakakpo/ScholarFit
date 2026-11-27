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
    from . import models  # noqa: F401  (enregistre les tables)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Mise à niveau légère d'une base existante : ajoute les colonnes apparues depuis sa création
    (create_all ne crée que les tables manquantes). Pour la production : passer à Alembic."""
    import json

    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
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
