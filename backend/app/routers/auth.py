import re
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, ratelimit
from ..config import get_settings
from ..db import get_db
from ..i18n import t
from ..mailer import reset_email, send_mail, verification_email
from ..models import Profile, User
from ..ratelimit import limit
from ..schemas import EmailIn, LoginIn, RegisterIn, ResetIn, TokenIn, TokenOut, UserOut, UserUpdate
from ..security import create_link_token, create_token, current_user, hash_password, read_link_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["comptes"])

# Un e-mail de confirmation ou de réinitialisation au plus par minute et par adresse
MAIL_COOLDOWN_SECONDS = 60
_last_mail: dict[tuple[str, str], float] = {}


def _cooldown_ok(kind: str, email: str) -> bool:
    now = time.monotonic()
    key = (kind, email)
    if now - _last_mail.get(key, -1e9) < MAIL_COOLDOWN_SECONDS:
        return False
    _last_mail[key] = now
    return True


def home_for(user: User) -> str:
    """Tableau de bord selon le rôle : administration, espace conseiller ou « Mes bourses »."""
    if user.is_admin:
        return "/admin"
    if user.is_advisor:
        return "/conseiller"
    return "/mes-bourses"


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw).strip()
    if len(name) < 2:
        raise HTTPException(422, t("Indiquez votre prénom ou un nom d'utilisateur (2 caractères minimum).", "Enter your first name or a username (at least 2 characters)."))
    if re.search(r"[<>@/\\]|https?:|www\.", name, re.I):
        raise HTTPException(422, t("Le nom d'utilisateur ne peut contenir ni adresse e-mail, ni lien, ni les signes < > / \\.", "The username cannot contain an email address, a link or the signs < > / \\."))
    return name[:80]


def _check_password(pw: str, email: str) -> None:
    if len(pw) < 8 or not any(ch.isalpha() for ch in pw) or not any(ch.isdigit() for ch in pw):
        raise HTTPException(422, t("Le mot de passe doit contenir au moins 8 caractères, dont une lettre et un chiffre.", "The password must have at least 8 characters, including a letter and a number."))
    if pw.strip().lower() == email or pw.lower() in email:
        raise HTTPException(422, t("Le mot de passe ne doit pas reprendre votre adresse e-mail.", "The password must not repeat your email address."))


def _send_verification(user: User, background: BackgroundTasks) -> None:
    s = get_settings()
    link = f"{s.site_url.rstrip('/')}/verifier-email?token={create_link_token(user, 'verify', s.verify_link_hours * 60)}"
    subject, text, html = verification_email(user.display_name, link, s.verify_link_hours, en=i18n.is_en())
    background.add_task(send_mail, user.email, subject, text, html)


def _grant_admin(user: User) -> None:
    """Droits d'administrateur seulement pour une adresse de ADMIN_EMAILS dont la boîte a été confirmée."""
    if user.email_verified and user.email in get_settings().admin_email_list:
        user.is_admin = True


@router.post("/register", response_model=TokenOut, status_code=201,
             dependencies=[Depends(limit("register", 10, 3600))])
def register(body: RegisterIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    name = _clean_name(body.name) if body.name.strip() else ""
    _check_password(body.password, email)
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(409, t("Un compte existe déjà avec cet e-mail : connectez-vous ou utilisez une autre adresse.", "An account already exists with this email: sign in or use another address."))
    user = User(email=email, name=name, password_hash=hash_password(body.password), is_admin=False)
    user.profile = Profile()
    db.add(user)
    db.commit()
    _cooldown_ok("verify", email)
    _send_verification(user, background)
    return TokenOut(access_token=create_token(user), home="/profil")


@router.post("/login", response_model=TokenOut, dependencies=[Depends(limit("login", 10, 600))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.strip().lower())).first()
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
    user = user_from_link(db, body.token, VERIFY_EMAIL)
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
def reset_password(body: ResetPasswordIn, request: Request, response: Response, db: Session = Depends(get_db)):
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
    clear_session_cookie(response)


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


# ---------- Confirmation de l'adresse e-mail ----------
@router.post("/verification/envoyer")
def resend_verification(background: BackgroundTasks, user: User = Depends(current_user)):
    if user.email_verified:
        return {"sent": False, "already_verified": True}
    if not _cooldown_ok("verify", user.email):
        raise HTTPException(429, t("Un e-mail vient d'être envoyé. Patientez une minute avant d'en demander un autre.", "An email was just sent. Wait a minute before asking for another one."))
    _send_verification(user, background)
    return {"sent": True, "already_verified": False}


@router.post("/verification")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user = read_link_token(body.token, "verify", db)
    if user is None:
        raise HTTPException(400, t("Ce lien de confirmation n'est plus valable. Connectez-vous et demandez-en un nouveau.", "This confirmation link is no longer valid. Sign in and ask for a new one."))
    user.email_verified = True
    _grant_admin(user)
    db.commit()
    return {"verified": True, "email": user.email}


# ---------- Mot de passe oublié ----------
@router.post("/mot-de-passe-oublie", dependencies=[Depends(limit("reset", 5, 3600))])
def forgot_password(body: EmailIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Envoie un lien de réinitialisation. La réponse est la même que le compte existe ou non
    (on ne révèle pas quelles adresses ont un compte)."""
    email = body.email.strip().lower()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None and _cooldown_ok("reset", email):
        s = get_settings()
        link = f"{s.site_url.rstrip('/')}/reinitialiser?token={create_link_token(user, 'reset', s.reset_link_minutes)}"
        subject, text, html = reset_email(user.display_name, link, s.reset_link_minutes, en=i18n.is_en())
        background.add_task(send_mail, user.email, subject, text, html)
    return {"sent": True}


@router.post("/reinitialiser", response_model=TokenOut, dependencies=[Depends(limit("reset2", 20, 3600))])
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    user = read_link_token(body.token, "reset", db)
    if user is None:
        raise HTTPException(400, t("Ce lien n'est plus valable (expiré ou déjà utilisé). Demandez-en un nouveau.", "This link is no longer valid (expired or already used). Ask for a new one."))
    _check_password(body.password, user.email)
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # le lien a été ouvert depuis la boîte mail
    _grant_admin(user)
    db.commit()
    return TokenOut(access_token=create_token(user), home=home_for(user))


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
