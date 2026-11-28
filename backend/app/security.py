"""Mots de passe (PBKDF2, bibliothèque standard), session et liens signés.

La session est un jeton JWT rangé dans un cookie httpOnly (illisible par le JavaScript de la page,
donc hors de portée d'une faille XSS), SameSite=Lax et Secure hors développement. Chaque jeton
porte la `token_version` du compte : changer de mot de passe invalide toutes les sessions ouvertes.
"""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from . import i18n
from .config import get_settings
from .db import get_db
from .i18n import t
from .models import User

ITERATIONS = 310_000
SESSION = "session"
VERIFY_EMAIL = "verifier_email"
RESET_PASSWORD = "reinitialiser"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


# Calcul factice pour qu'une connexion avec un e-mail inconnu prenne autant de temps qu'avec un vrai
# compte (sinon la durée de la réponse révèle quels e-mails ont un compte).
_DUMMY_HASH = hash_password(os.urandom(12).hex())


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def password_problem(password: str, email: str) -> str | None:
    if len(password) < 8 or not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return t("Le mot de passe doit contenir au moins 8 caractères, dont une lettre et un chiffre.",
                 "The password must be at least 8 characters long, with a letter and a digit.")
    if password.strip().lower() == email or password.lower() in email:
        return t("Le mot de passe ne doit pas reprendre votre adresse e-mail.", "The password must not contain your e-mail address.")
    return None


# ---------- Jetons ----------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def create_session_token(user: User, auth_time: int | None = None) -> str:
    s = get_settings()
    now = _now()
    return _encode({
        "sub": str(user.id), "typ": SESSION, "ver": user.token_version or 0,
        "iat": int(now.timestamp()), "auth": auth_time or int(now.timestamp()),
        "exp": now + timedelta(minutes=s.token_expire_minutes),
    })


def create_link_token(user: User, purpose: str, minutes: int) -> str:
    """Lien envoyé par e-mail. Lié à l'adresse et à la version du compte : un lien de
    réinitialisation ne sert qu'une fois (le mot de passe change la version)."""
    return _encode({
        "sub": str(user.id), "typ": purpose, "ver": user.token_version or 0, "email": user.email,
        "exp": _now() + timedelta(minutes=minutes),
    })


def decode(token: str, purpose: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == purpose else None


def user_from_link(db: Session, token: str, purpose: str) -> User | None:
    payload = decode(token, purpose)
    if not payload:
        return None
    try:
        user = db.get(User, int(payload["sub"]))
    except (KeyError, ValueError):
        return None
    if user is None or payload.get("ver") != (user.token_version or 0) or payload.get("email") != user.email:
        return None
    return user


# ---------- Cookie de session ----------
def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name, token, max_age=s.token_expire_minutes * 60, httponly=True,
        secure=not s.is_dev, samesite="lax", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/", httponly=True, secure=not s.is_dev, samesite="lax")


def start_session(response: Response, user: User) -> None:
    set_session_cookie(response, create_session_token(user))


def renewed_session(token: str) -> str | None:
    """Nouveau jeton si la session a consommé plus de la moitié de sa durée, sans dépasser
    session_max_days depuis la connexion. La version du compte est reprise telle quelle : une
    session révoquée reste refusée par current_user."""
    s = get_settings()
    payload = decode(token, SESSION)
    if not payload:
        return None
    now = int(_now().timestamp())
    lifetime = s.token_expire_minutes * 60
    if payload["exp"] - now > lifetime / 2 or now - int(payload.get("auth", now)) > s.session_max_days * 86400:
        return None
    fresh = _now()
    return _encode({**payload, "iat": int(fresh.timestamp()), "exp": fresh + timedelta(seconds=lifetime)})


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, t("Connexion requise", "Please sign in"))
    payload = decode(token, SESSION)
    user = None
    if payload:
        try:
            user = db.get(User, int(payload["sub"]))
        except (KeyError, ValueError):
            user = None
        if user is not None and payload.get("ver") != (user.token_version or 0):
            user = None  # mot de passe changé depuis : session révoquée
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, t("Session expirée, reconnectez-vous", "Session expired, please sign in again"))
    if i18n.explicit() and user.lang != i18n.lang():  # langue retenue pour les alertes et e-mails
        user.lang = i18n.lang()
        db.commit()
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, t("Réservé aux administrateurs", "Administrators only"))
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, {
            "code": "email_non_verifie",
            "message": t("Confirmez d'abord votre adresse e-mail (lien reçu à l'inscription, ou « Renvoyer le lien » en haut de la page).",
                         "Please confirm your e-mail address first (link sent at sign-up, or “Resend the link” at the top of the page)."),
        })
    return user


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    if not request.cookies.get(get_settings().session_cookie_name):
        return None
    try:
        return current_user(request, db)
    except HTTPException:
        return None
