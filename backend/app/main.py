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
    if not settings.demo_accounts:
        return
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


@app.get("/api/health")
def health():
    return {"ok": True, "ia": "claude" if settings.ai_enabled else "hors-ligne (règles)", "modele": settings.claude_model if settings.ai_enabled else None}
