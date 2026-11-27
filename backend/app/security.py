"""Mots de passe (PBKDF2, bibliothèque standard) et jetons JWT."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import i18n
from .config import get_settings
from .i18n import t
from .db import get_db
from .models import User

ITERATIONS = 310_000
bearer = HTTPBearer(auto_error=False)


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


def create_token(user_id: int) -> str:
    s = get_settings()
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=s.token_expire_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, t("Connexion requise", "Please sign in"))
    try:
        payload = jwt.decode(creds.credentials, get_settings().secret_key, algorithms=["HS256"])
        # un lien reçu par e-mail (confirmation, mot de passe oublié) n'ouvre pas de session
        user = None if "purpose" in payload else db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
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


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    if creds is None:
        return None
    try:
        return current_user(creds, db)
    except HTTPException:
        return None


# ---------- Liens envoyés par e-mail (confirmation de l'adresse, mot de passe oublié) ----------
# Jetons signés, sans table en base. Le lien de réinitialisation contient une empreinte du mot de
# passe actuel : il ne sert qu'une fois (dès que le mot de passe change, il n'est plus valable).
def _pw_fingerprint(user: User) -> str:
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def create_link_token(user: User, purpose: str, minutes: int) -> str:
    payload = {"sub": str(user.id), "purpose": purpose, "email": user.email,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}
    if purpose == "reset":
        payload["pw"] = _pw_fingerprint(user)
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def read_link_token(token: str, purpose: str, db: Session) -> User | None:
    """Utilisateur du lien, ou None si le lien est faux, expiré ou déjà utilisé."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        if payload.get("purpose") != purpose:
            return None
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
    if user is None or user.email != payload.get("email"):
        return None
    if purpose == "reset" and payload.get("pw") != _pw_fingerprint(user):
        return None
    return user
