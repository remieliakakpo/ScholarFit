"""Comptes : inscription, connexion par cookie httpOnly, vérification de l'adresse, mot de passe oublié."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ratelimit
from ..config import get_settings
from ..db import get_db
from ..i18n import lang, t
from ..mailer import link, send_mail
from ..models import Profile, User
from ..schemas import ChangePasswordIn, EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn, UserOut
from ..security import (
    RESET_PASSWORD, VERIFY_EMAIL, burn_password_check, clear_session_cookie, create_link_token, current_user,
    hash_password, password_problem, start_session, user_from_link, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["comptes"])

MIN = 60
VERIFY_LINK_MINUTES = 48 * 60
RESET_LINK_MINUTES = 60


def _norm(email: str) -> str:
    return email.strip().lower()


def _send_verification(user: User) -> None:
    url = link(f"/verifier-email?token={create_link_token(user, VERIFY_EMAIL, VERIFY_LINK_MINUTES)}")
    if user.lang == "en":
        send_mail(user.email, "Confirm your ScholarFit e-mail address",
                  f"Hello,\n\nTo confirm your e-mail address, open this link (valid for 48 hours):\n{url}\n\n"
                  "If you did not create a ScholarFit account, ignore this message.\n")
    else:
        send_mail(user.email, "Confirmez votre adresse e-mail ScholarFit",
                  f"Bonjour,\n\nPour confirmer votre adresse e-mail, ouvrez ce lien (valable 48 heures) :\n{url}\n\n"
                  "Si vous n'avez pas créé de compte ScholarFit, ignorez ce message.\n")


def _send_reset(user: User) -> None:
    url = link(f"/reinitialiser-mot-de-passe?token={create_link_token(user, RESET_PASSWORD, RESET_LINK_MINUTES)}")
    if user.lang == "en":
        send_mail(user.email, "Reset your ScholarFit password",
                  f"Hello,\n\nTo choose a new password, open this link (valid for 1 hour, usable once):\n{url}\n\n"
                  "If you did not ask for this, ignore this message: your password stays the same.\n")
    else:
        send_mail(user.email, "Réinitialisez votre mot de passe ScholarFit",
                  f"Bonjour,\n\nPour choisir un nouveau mot de passe, ouvrez ce lien (valable 1 heure, une seule fois) :\n{url}\n\n"
                  "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : votre mot de passe ne change pas.\n")


def _grant_admin_if_listed(user: User) -> None:
    """Les adresses de ADMIN_EMAILS deviennent administratrices seulement une fois l'adresse prouvée :
    sinon, n'importe qui pourrait s'inscrire avec une de ces adresses avant son titulaire."""
    if user.email_verified and user.email in get_settings().admin_email_list:
        user.is_admin = True


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, request: Request, response: Response, background: BackgroundTasks, db: Session = Depends(get_db)):
    ratelimit.check(f"register:{ratelimit.client_ip(request)}", 5, 15 * MIN)
    email = _norm(body.email)
    if not body.accept_terms:
        raise HTTPException(422, t("Acceptez les conditions d'utilisation et la politique de confidentialité pour créer un compte.",
                                   "Please accept the terms of use and the privacy policy to create an account."))
    problem = password_problem(body.password, email)
    if problem:
        raise HTTPException(422, problem)
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, t("Un compte existe déjà avec cet e-mail : connectez-vous ou utilisez une autre adresse.",
                                   "An account already exists with this e-mail: sign in or use another address."))
    now = datetime.now(timezone.utc)
    user = User(email=email, password_hash=hash_password(body.password), terms_accepted_at=now)
    user.lang = lang()
    user.profile = Profile()
    db.add(user)
    db.commit()
    background.add_task(_send_verification, user)
    start_session(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = _norm(body.email)
    ratelimit.check(f"login-ip:{ratelimit.client_ip(request)}", 20, 15 * MIN)
    fail_key = f"login-fail:{email}"
    if ratelimit.count(fail_key, 15 * MIN) >= 5:  # 5 erreurs sur un compte : pause de 15 min
        raise HTTPException(429, t("Trop de tentatives sur ce compte. Réessayez dans 15 min ou utilisez « Mot de passe oublié ».",
                                   "Too many attempts on this account. Try again in 15 min or use “Forgot password”."),
                            headers={"Retry-After": str(15 * MIN)})
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        burn_password_check(body.password)
    if not user or not verify_password(body.password, user.password_hash):
        ratelimit.record(fail_key)
        raise HTTPException(401, t("E-mail ou mot de passe incorrect", "Incorrect e-mail or password"))
    ratelimit.reset(fail_key)
    start_session(response, user)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/email-disponible")
def email_available(email: str, request: Request, db: Session = Depends(get_db)):
    """Pour le formulaire d'inscription : prévient tout de suite si un compte existe déjà.
    Limité pour qu'on ne puisse pas tester des listes d'adresses."""
    ratelimit.check(f"email-check:{ratelimit.client_ip(request)}", 30, 15 * MIN)
    return {"available": db.scalars(select(User).where(User.email == _norm(email))).first() is None}


@router.post("/verifier-email", response_model=UserOut)
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user = user_from_link(db, body.token, VERIFY_EMAIL)
    if user is None:
        raise HTTPException(400, t("Ce lien n'est plus valable. Connectez-vous puis demandez un nouveau lien.",
                                   "This link is no longer valid. Sign in, then ask for a new link."))
    if not user.email_verified:
        user.email_verified_at = datetime.now(timezone.utc)
    _grant_admin_if_listed(user)
    db.commit()
    return user


@router.post("/renvoyer-verification", status_code=204)
def resend_verification(background: BackgroundTasks, user: User = Depends(current_user)):
    if user.email_verified:
        return
    ratelimit.check(f"resend:{user.id}", 3, 60 * MIN)
    background.add_task(_send_verification, user)


@router.post("/mot-de-passe-oublie")
def forgot_password(body: EmailIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Même réponse que l'adresse ait un compte ou non (on ne révèle pas qui est inscrit)."""
    ratelimit.check(f"forgot-ip:{ratelimit.client_ip(request)}", 5, 15 * MIN)
    email = _norm(body.email)
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None and ratelimit.count(f"forgot:{email}", 60 * MIN) < 3:
        ratelimit.record(f"forgot:{email}")
        background.add_task(_send_reset, user)
    return {"message": t("Si un compte existe avec cette adresse, un e-mail vient d'être envoyé avec un lien valable 1 heure.",
                         "If an account exists with this address, an e-mail has just been sent with a link valid for 1 hour.")}


@router.post("/reinitialiser-mot-de-passe", status_code=204)
def reset_password(body: ResetPasswordIn, response: Response, db: Session = Depends(get_db)):
    user = user_from_link(db, body.token, RESET_PASSWORD)
    if user is None:
        raise HTTPException(400, t("Ce lien n'est plus valable (il sert une seule fois, pendant 1 heure). Demandez-en un nouveau.",
                                   "This link is no longer valid (single use, for 1 hour). Ask for a new one."))
    problem = password_problem(body.password, user.email)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.password)
    user.token_version = (user.token_version or 0) + 1  # déconnecte partout, le lien ne resservira pas
    if not user.email_verified:  # le lien reçu par e-mail prouve l'adresse
        user.email_verified_at = datetime.now(timezone.utc)
        _grant_admin_if_listed(user)
    db.commit()
    ratelimit.reset(f"login-fail:{user.email}")
    clear_session_cookie(response)


@router.post("/changer-mot-de-passe", response_model=UserOut)
def change_password(body: ChangePasswordIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.check(f"change-pw:{user.id}", 5, 15 * MIN)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, t("Mot de passe actuel incorrect", "Current password is incorrect"))
    problem = password_problem(body.new_password, user.email)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1  # les autres appareils sont déconnectés
    db.commit()
    start_session(response, user)
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.delete("/me", status_code=204)
def delete_account(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Suppression du compte en un clic : profil, CV, lettres, candidatures, accompagnements et alertes."""
    if user.advisor is not None:  # ses candidats repassent en attente d'un nouveau conseiller
        for c in user.advisor.coachings:
            if c.status == "en_cours":
                c.status = "demande"
    db.delete(user)
    db.commit()
    clear_session_cookie(response)
