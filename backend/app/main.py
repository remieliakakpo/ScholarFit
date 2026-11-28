import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .i18n import LangMiddleware
from . import scheduler
from .routers import admin, ai, applications, auth, chat, coaching, community, monitoring, profile, questionnaire, scholarships

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

if settings.sentry_dsn:  # suivi des erreurs (Sentry ou compatible), seulement si configuré
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,  # ni cookies ni adresses e-mail envoyés à Sentry
        )
    except ImportError:
        logging.getLogger(__name__).warning("SENTRY_DSN est défini mais sentry-sdk n'est pas installé")



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

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
UPLOAD_LIMIT = 6 * 1024 * 1024  # CV : 5 Mo + enveloppe multipart


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Protection CSRF, renouvellement de la session et en-têtes de sécurité.

    CSRF : toute requête qui modifie quelque chose doit porter l'en-tête X-Requested-With (le site
    l'ajoute à chaque appel). Un autre site ne peut pas l'ajouter sans l'accord de CORS, et un
    formulaire HTML ne peut pas l'envoyer. Le cookie SameSite=Lax est une seconde barrière."""
    if request.method in UNSAFE and request.url.path.startswith("/api/") and not request.headers.get("x-requested-with"):
        return JSONResponse({"detail": "En-tête X-Requested-With manquant (protection CSRF)"}, status_code=403)
    if request.method in UNSAFE:
        limit = UPLOAD_LIMIT if (request.url.path == "/api/profile/cv" or request.url.path.endswith("/preuve")) else int(settings.max_request_mb * 1024 * 1024)
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = limit + 1
        if size > limit:
            return JSONResponse({"detail": "Requête trop volumineuse"}, status_code=413)
        if "content-length" not in request.headers and request.headers.get("transfer-encoding"):
            return JSONResponse({"detail": "Taille de la requête requise (Content-Length)"}, status_code=411)
    response = await call_next(request)
    token = request.cookies.get(settings.session_cookie_name)
    if request.method in UNSAFE and request.url.path.startswith("/api/admin/") and response.status_code < 400:
        from starlette.concurrency import run_in_threadpool

        from .audit import record_admin_request
        from .security import SESSION, decode

        payload = decode(token, SESSION) if token else None
        user_id = int(payload["sub"]) if payload and str(payload.get("sub", "")).isdigit() else None
        await run_in_threadpool(record_admin_request, request, response.status_code, user_id)
    if token and response.status_code < 400 and "set-cookie" not in response.headers:
        from .security import renewed_session, set_session_cookie

        fresh = renewed_session(token)
        if fresh:
            set_session_cookie(response, fresh)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if token and request.url.path.startswith("/api/"):  # réponse personnelle : jamais en cache
        response.headers.setdefault("Cache-Control", "private, no-store")
    return response


app.add_middleware(LangMiddleware)  # ?lang=en ou cookie sf_lang=en : textes de l'API en anglais
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, scholarships, community, monitoring, profile, chat, applications, ai, admin, coaching, questionnaire):
    app.include_router(r.router)
app.include_router(coaching.admin_router)
app.include_router(payments.admin_router)


API_VERSION = "2026-11-27b"


@app.get("/api/health")
def health():
    # "version" permet de vérifier en ligne (https://…railway.app/api/health) que Railway tourne bien le dernier code.
    return {"ok": True, "version": API_VERSION, "ia": "claude" if settings.ai_enabled else "hors-ligne (règles)", "modele": settings.claude_model if settings.ai_enabled else None}
