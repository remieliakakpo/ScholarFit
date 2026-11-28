"""Comptes : inscription, connexion par cookie httpOnly, vérification de l'adresse, mot de passe oublié."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, ratelimit
from ..config import get_settings
from ..db import get_db
from ..i18n import lang, t
from ..mailer import link, reset_email, send_mail, verification_email
from ..models import Profile, User
from ..schemas import ChangePasswordIn, EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn, UserOut, UserUpdate
from ..security import (
    RESET_PASSWORD, VERIFY_EMAIL, burn_password_check, clear_session_cookie, create_link_token, current_user,
    hash_password, password_problem, start_session, user_from_link, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["comptes"])

MIN = 60


def _norm(email: str) -> str:
    return email.strip().lower()


def _send_verification(user: User, name: str) -> None:
    st = get_settings()
    url = link(f"/verifier-email?token={create_link_token(user, VERIFY_EMAIL, st.verify_link_hours * 60)}")
    subject, text, html = verification_email(name, url, st.verify_link_hours, en=user.lang == "en")
    send_mail(user.email, subject, text, html)


def _send_reset(user: User, name: str) -> None:
    st = get_settings()
    url = link(f"/reinitialiser?token={create_link_token(user, RESET_PASSWORD, st.reset_link_minutes)}")
    subject, text, html = reset_email(name, url, st.reset_link_minutes, en=user.lang == "en")
    send_mail(user.email, subject, text, html)


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw).strip()
    if len(name) < 2:
        raise HTTPException(422, t("Indiquez votre prénom ou un nom d'utilisateur (2 caractères minimum).",
                                   "Enter your first name or a username (at least 2 characters)."))
    if re.search(r"[<>@/\\]|https?:|www\.", name, re.I):
        raise HTTPException(422, t("Le nom d'utilisateur ne peut contenir ni adresse e-mail, ni lien, ni les signes < > / \\.",
                                   "The username cannot contain an email address, a link or the signs < > / \\."))
    return name[:80]


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
    name = _clean_name(body.name) if body.name.strip() else ""
    now = datetime.now(timezone.utc)
    user = User(email=email, name=name, password_hash=hash_password(body.password), terms_accepted_at=now)
    user.lang = lang()
    user.profile = Profile()
    db.add(user)
    db.commit()
    background.add_task(_send_verification, user, user.display_name)
    ratelimit.record(f"resend-1min:{user.id}")  # l'e-mail vient de partir : pas de second envoi tout de suite
    start_session(response, user)
    out = UserOut.model_validate(user)
    out.home = "/profil"  # premier passage : compléter son profil
    return out


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
    if user.is_admin:  # chaque ouverture de session administrateur est tracée
        audit.record(db, user, "connexion administrateur", target_type="users", target_id=user.id, request=request)
        db.commit()
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
    return _verify(body.token, db)


@router.post("/verification")
def verify_email_page(body: TokenIn, db: Session = Depends(get_db)):
    user = _verify(body.token, db)
    return {"verified": True, "email": user.email}


def _verify(token: str, db: Session) -> User:
    user = user_from_link(db, token, VERIFY_EMAIL)
    if user is None:
        raise HTTPException(400, t("Ce lien n'est plus valable. Connectez-vous puis demandez un nouveau lien.",
                                   "This link is no longer valid. Sign in, then ask for a new link."))
    if not user.email_verified:
        user.email_verified_at = datetime.now(timezone.utc)
    was_admin = user.is_admin
    _grant_admin_if_listed(user)
    if user.is_admin and not was_admin:
        audit.record(db, user, "droits administrateur accordés (ADMIN_EMAILS)", target_type="users", target_id=user.id)
    db.commit()
    return user


@router.post("/renvoyer-verification", status_code=204)
def resend_verification(background: BackgroundTasks, user: User = Depends(current_user)):
    resend_verification_page(background, user)


@router.post("/verification/envoyer")
def resend_verification_page(background: BackgroundTasks, user: User = Depends(current_user)):
    if user.email_verified:
        return {"sent": False, "already_verified": True}
    if ratelimit.count(f"resend-1min:{user.id}", MIN):  # un e-mail par minute au plus
        raise HTTPException(429, t("Un e-mail vient d'être envoyé. Patientez une minute avant d'en demander un autre.",
                                   "An email was just sent. Wait a minute before asking for another one."))
    ratelimit.check(f"resend:{user.id}", 3, 60 * MIN)
    ratelimit.record(f"resend-1min:{user.id}")
    background.add_task(_send_verification, user, user.display_name)
    return {"sent": True, "already_verified": False}


@router.post("/mot-de-passe-oublie")
def forgot_password(body: EmailIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Même réponse que l'adresse ait un compte ou non (on ne révèle pas qui est inscrit)."""
    ratelimit.check(f"forgot-ip:{ratelimit.client_ip(request)}", 5, 15 * MIN)
    email = _norm(body.email)
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None and ratelimit.count(f"forgot:{email}", 60 * MIN) < 3:
        ratelimit.record(f"forgot:{email}")
        background.add_task(_send_reset, user, user.display_name)
    return {"sent": True,
            "message": t("Si un compte existe avec cette adresse, un e-mail vient d'être envoyé avec un lien valable 1 heure.",
                         "If an account exists with this address, an e-mail has just been sent with a link valid for 1 hour.")}


@router.post("/reinitialiser-mot-de-passe", status_code=204)
def reset_password(body: ResetPasswordIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _reset(body, request, db)
    clear_session_cookie(response)


@router.post("/reinitialiser", response_model=UserOut)
def reset_password_page(body: ResetPasswordIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Page « Choisir un nouveau mot de passe » : les autres appareils sont déconnectés, ce navigateur
    reste connecté avec le nouveau mot de passe."""
    user = _reset(body, request, db)
    start_session(response, user)
    return user


def _reset(body: ResetPasswordIn, request: Request, db: Session) -> User:
    ratelimit.check(f"reset-ip:{ratelimit.client_ip(request)}", 20, 60 * MIN)
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
    audit.record(db, user, "mot de passe réinitialisé (lien e-mail)", target_type="users", target_id=user.id, request=request)
    db.commit()
    ratelimit.reset(f"login-fail:{user.email}")
    return user


@router.post("/changer-mot-de-passe", response_model=UserOut)
def change_password(body: ChangePasswordIn, request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.check(f"change-pw:{user.id}", 5, 15 * MIN)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, t("Mot de passe actuel incorrect", "Current password is incorrect"))
    problem = password_problem(body.new_password, user.email)
    if problem:
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1  # les autres appareils sont déconnectés
    audit.record(db, user, "mot de passe changé", target_type="users", target_id=user.id, request=request)
    db.commit()
    start_session(response, user)
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Changer son nom d'utilisateur (affiché dans « Salut, … »)."""
    user.name = _clean_name(body.name)
    db.commit()
    return user


@router.delete("/me", status_code=204)
def delete_account(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Suppression du compte en un clic : profil, CV, lettres, candidatures, accompagnements et alertes."""
    from sqlalchemy import update

    from ..models import AuditLog, ScholarshipReport

    # Signalements gardés (utiles à la qualité des fiches) mais détachés du compte ; le journal
    # d'audit garde l'adresse en clair (sécurité), plus le lien vers le compte supprimé.
    db.execute(update(ScholarshipReport).where(ScholarshipReport.user_id == user.id).values(user_id=None))
    db.execute(update(ScholarshipReport).where(ScholarshipReport.resolved_by_id == user.id).values(resolved_by_id=None))
    db.execute(update(AuditLog).where(AuditLog.actor_id == user.id).values(actor_id=None))
    audit.record(db, None, "compte supprimé par son titulaire", target_type="users", target_id=user.id, request=request,
                 details={"email": user.email})
    if user.advisor is not None:  # ses candidats repassent en attente d'un nouveau conseiller
        for c in user.advisor.coachings:
            if c.status == "en_cours":
                c.status = "demande"
    from .. import proofs

    proof_files = [o.proof_path for o in user.credit_orders if o.proof_path]
    db.delete(user)
    db.commit()
    for rel in proof_files:  # captures de reçus effacées avec le compte
        proofs.delete_proof(rel)
    clear_session_cookie(response)
