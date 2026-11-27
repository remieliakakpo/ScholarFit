import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .i18n import LangMiddleware
from . import scheduler
from .routers import admin, ai, applications, auth, chat, coaching, payments, profile, questionnaire, scholarships, seo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
settings = get_settings()

if settings.sentry_dsn:
    # Suivi des erreurs en ligne : chaque erreur 500 est envoyée à Sentry avec sa pile d'appels
    # (paquet facultatif « sentry-sdk », listé dans requirements.txt).
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.0, send_default_pii=False,
                        environment="production" if settings.is_production else "local")
    except ImportError:  # pragma: no cover
        logging.getLogger("scholarfit").warning("SENTRY_DSN défini mais le paquet sentry-sdk n'est pas installé.")



def _load_translations() -> None:
    """Version anglaise des fiches de départ (fichier fourni, sans IA)."""
    from .db import SessionLocal
    from .translate import load_seed_translations

    db = SessionLocal()
    try:
        load_seed_translations(db)
    except Exception:  # noqa: BLE001 - le site reste en français pour ces fiches
        logging.getLogger(__name__).exception("Traductions de départ non chargées")
    finally:
        db.close()


def _demo_accounts() -> None:
    """Identifiants du README toujours valables, même si « app.cli seed » n'a pas été lancé."""
    from .db import SessionLocal
    from .demo import ensure_demo_accounts

    db = SessionLocal()
    try:
        ensure_demo_accounts(db)
    except Exception:  # noqa: BLE001 - l'API démarre quand même
        logging.getLogger(__name__).exception("Comptes de démo non créés")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _load_translations()
    _demo_accounts()
    from .launch import warn_at_startup

    warn_at_startup()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    lifespan=lifespan,
    title="ScholarFit API",
    description="Collecte de bourses d'études, matching profil / bourses, assistant de recherche, CV et lettres, accompagnement des candidatures.",
    version="0.2.0",
)
app.add_middleware(LangMiddleware)  # ?lang=en ou cookie sf_lang=en : textes de l'API en anglais
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, scholarships, profile, chat, applications, ai, admin, coaching, questionnaire, payments, seo):
    app.include_router(r.router)
app.include_router(coaching.admin_router)
app.include_router(payments.admin_router)


API_VERSION = "2026-11-27b"


@app.get("/api/health")
def health():
    # "version" permet de vérifier en ligne (https://…railway.app/api/health) que Railway tourne bien le dernier code.
    return {"ok": True, "version": API_VERSION, "ia": "claude" if settings.ai_enabled else "hors-ligne (règles)", "modele": settings.claude_model if settings.ai_enabled else None}
