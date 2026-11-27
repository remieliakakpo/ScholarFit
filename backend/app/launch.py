"""Outils de mise en ligne : vérification des réglages et sauvegarde portable de la base.

    python -m app.cli check-config     liste ce qui manque avant d'ouvrir le site au public
    python -m app.cli backup           exporte toutes les tables dans backups/scholarfit-AAAAMMJJ-HHMM.json.gz
"""
from __future__ import annotations

import base64
import gzip
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, engine
from .models import User
from .security import verify_password

log = logging.getLogger("lancement")
DEMO_ACCOUNTS = {"admin@example.org": "admin12345", "demo@example.org": "demo12345", "conseiller@example.org": "conseil12345"}


def check_config(db: Session | None = None) -> list[tuple[str, str]]:
    """Liste des problèmes : (BLOQUANT | CONSEIL, message)."""
    s = get_settings()
    out: list[tuple[str, str]] = []
    if s.secret_key.startswith("dev-secret") or len(s.secret_key) < 32:
        if s.is_production:
            out.append(("CONSEIL", "SECRET_KEY est la valeur par défaut : le site utilise une clé aléatoire gardée dans la base (app_settings), ce qui est sûr. Pour la maîtriser vous-même, mettez votre propre clé : python -c \"import secrets; print(secrets.token_hex(32))\"."))
        else:
            out.append(("BLOQUANT", "SECRET_KEY est la valeur par défaut ou trop courte : générez-en une avec python -c \"import secrets; print(secrets.token_hex(32))\"."))
    if s.database_url.startswith("sqlite"):
        out.append(("BLOQUANT", "DATABASE_URL utilise SQLite : en ligne, la base serait effacée à chaque redéploiement. Utilisez PostgreSQL."))
    if not s.site_url.startswith("https://"):
        out.append(("BLOQUANT", f"SITE_URL = {s.site_url} : mettez l'adresse publique du site en https (liens des e-mails, retour après paiement)."))
    if not s.api_public_url.startswith("https://"):
        out.append(("BLOQUANT", f"API_PUBLIC_URL = {s.api_public_url} : mettez l'adresse publique de l'API en https (notifications CinetPay)."))
    if s.payment_provider == "simulation":
        if s.is_production:
            out.append(("BLOQUANT", "PAYMENT_PROVIDER=simulation : en ligne, le site bascule automatiquement en paiement manuel (validation dans /admin) pour éviter les paiements factices. Mettez cinetpay avec CINETPAY_APIKEY et CINETPAY_SITE_ID pour le paiement en ligne."))
        else:
            out.append(("BLOQUANT", "PAYMENT_PROVIDER=simulation : les paiements sont factices. Mettez cinetpay avec CINETPAY_APIKEY et CINETPAY_SITE_ID."))
    elif s.payment_provider == "cinetpay":
        if not (s.cinetpay_apikey and s.cinetpay_site_id):
            out.append(("BLOQUANT", "CINETPAY_APIKEY et CINETPAY_SITE_ID sont nécessaires (tableau de bord CinetPay > Intégrations)."))
        if not s.cinetpay_secret_key:
            out.append(("CONSEIL", "CINETPAY_SECRET_KEY vide : la signature des notifications n'est pas vérifiée (le statut est de toute façon revérifié auprès de CinetPay)."))
    backend = s.mail_backend
    if backend == "console":
        out.append(("BLOQUANT", "Aucun e-mail ne part (rappels, reçus, confirmation d'adresse) : configurez EMAIL_BACKEND=brevo (ou SMTP_HOST)."))
    elif backend == "brevo" and not s.brevo_api_key:
        out.append(("BLOQUANT", "BREVO_API_KEY manquante."))
    elif backend == "resend" and not s.resend_api_key:
        out.append(("BLOQUANT", "RESEND_API_KEY manquante."))
    elif backend == "smtp" and not s.smtp_host:
        out.append(("BLOQUANT", "SMTP_HOST manquant."))
    if "scholarfit.local" in s.smtp_from or "example" in s.smtp_from:
        out.append(("BLOQUANT", f"SMTP_FROM = {s.smtp_from} : mettez une adresse de votre domaine, validée chez votre service d'envoi (ex. ScholarFit <no-reply@votre-domaine.org>)."))
    if s.demo_accounts and not s.is_production:
        out.append(("CONSEIL", "DEMO_ACCOUNTS=true : pratique en local. En ligne (APP_ENV=production ou PostgreSQL), les comptes de démonstration sont désactivés automatiquement."))
    if not s.app_env:
        out.append(("CONSEIL", "APP_ENV vide : mettez APP_ENV=production sur Railway pour activer toutes les protections de mise en ligne (elles s'activent déjà dès que la base est PostgreSQL)."))
    if s.admin_email_list == ["admin@example.org"]:
        out.append(("BLOQUANT", "ADMIN_EMAILS vaut encore admin@example.org : mettez votre propre adresse."))
    if not any(o.startswith("https://") for o in s.cors_origin_list):
        out.append(("CONSEIL", "CORS_ORIGINS ne contient aucune adresse https : ajoutez l'adresse du site si le navigateur appelle l'API directement."))
    if not s.reliefweb_appname:
        out.append(("CONSEIL", "RELIEFWEB_APPNAME vide : les stages des organisations internationales ne sont pas collectés."))
    if not s.anthropic_api_key:
        out.append(("CONSEIL", "ANTHROPIC_API_KEY vide : CV, lettres et découverte de bourses fonctionnent en mode hors-ligne."))
    if s.auto_collect_hours <= 0:
        out.append(("CONSEIL", "AUTO_COLLECT_HOURS=0 : planifiez « python -m app.cli nightly » une fois par jour, sinon la base ne se met plus à jour."))
    if db is not None:
        for email, pwd in DEMO_ACCOUNTS.items():
            u = db.scalars(select(User).where(User.email == email)).first()
            if u is not None and verify_password(pwd, u.password_hash):
                out.append(("BLOQUANT", f"Le compte de démonstration {email} a encore son mot de passe public : changez-le ou supprimez le compte."))
    return out


def warn_at_startup() -> None:
    """Au démarrage de l'API en production (PostgreSQL), rappelle les réglages manquants dans les logs."""
    if not get_settings().is_production:
        return
    for level, msg in check_config():
        log.warning("[%s] %s", level, msg)


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"__b64__": base64.b64encode(bytes(v)).decode()}
    return v


def backup(db: Session, directory: str = "backups", keep: int = 14) -> Path:
    """Exporte toutes les tables (lisible, indépendant de SQLite ou PostgreSQL) et garde les `keep` dernières."""
    from . import models  # noqa: F401  (enregistre les tables)

    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = folder / f"scholarfit-{stamp}.json.gz"
    data: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            data[table.name] = [{k: _jsonable(v) for k, v in r.items()} for r in rows]
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"created_at": stamp, "tables": data}, f, ensure_ascii=False)
    old = sorted(folder.glob("scholarfit-*.json.gz"))[:-keep] if keep > 0 else []
    for p in old:
        p.unlink(missing_ok=True)
    return path
