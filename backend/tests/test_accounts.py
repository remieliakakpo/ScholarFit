"""Comptes : identifiants de démo, nom d'utilisateur, page d'arrivée, confirmation de l'e-mail, mot de passe oublié."""
import re

import pytest

from tests.conftest import login, session_headers

TERMS = {"accept_terms": True}


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("app.routers.auth.send_mail",
                        lambda to, subject, text, html=None, headers=None: sent.append({"to": to, "subject": subject, "text": text, "html": html}) or True)
    return sent


def _link(mail, path):
    m = re.search(rf"https?://\S+{path}\?token=(\S+)", mail["text"])
    assert m, mail["text"]
    return m.group(1)


def test_documented_demo_accounts_work_and_land_on_their_dashboard(client):
    for email, pw, home in [("demo@example.org", "demo12345", "/mes-bourses"), ("admin@example.org", "admin12345", "/admin"),
                            ("conseiller@example.org", "conseil12345", "/conseiller")]:
        r = client.post("/api/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 200, (email, r.text)
        assert r.json()["home"] == home
        client.cookies.clear()
    me = client.get("/api/auth/me", headers=login(client)).json()
    assert me["display_name"] == "Awa" and me["email_verified"] is True


def test_demo_password_repaired_at_startup(client):
    from app.db import SessionLocal
    from app.demo import ensure_demo_accounts
    from app.models import User
    from app.security import hash_password
    from sqlalchemy import select

    db = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "admin@example.org")).first()
        u.password_hash, u.is_admin = hash_password("autre-chose-1"), False
        db.commit()
        ensure_demo_accounts(db)
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"email": "admin@example.org", "password": "admin12345"})
    assert r.status_code == 200 and r.json()["home"] == "/admin"


def test_sqlite_path_does_not_depend_on_working_directory():
    from app.config import BACKEND_DIR, Settings

    url = Settings(database_url="sqlite:///./bourses.db").database_url
    assert url == "sqlite:///" + (BACKEND_DIR / "bourses.db").as_posix()


def test_register_with_name_greets_and_verifies_email(client, outbox):
    r = client.post("/api/auth/register", json={"name": "  Kossi  ", "email": "kossi@example.org", "password": "motdepasse1", **TERMS})
    assert r.status_code == 201, r.text
    assert r.json()["home"] == "/profil" and "access_token" not in r.json()
    h = session_headers(client, r)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["name"] == "Kossi" and me["display_name"] == "Kossi" and me["email_verified"] is False
    assert len(outbox) == 1 and outbox[0]["to"] == "kossi@example.org" and "Salut Kossi" in outbox[0]["text"]
    token = _link(outbox[0], "/verifier-email")
    # le lien n'ouvre pas de session
    assert client.get("/api/auth/me", headers={"Cookie": f"sf_session={token}"}).status_code == 401
    assert client.post("/api/auth/verification", json={"token": token + "x"}).status_code == 400
    assert client.post("/api/auth/verification", json={"token": token}).json()["verified"] is True
    assert client.get("/api/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/api/auth/verification/envoyer", headers=h).json()["already_verified"] is True
    # changer de nom
    assert client.patch("/api/auth/me", headers=h, json={"name": "Kossi A."}).json()["display_name"] == "Kossi A."
    assert client.patch("/api/auth/me", headers=h, json={"name": "x@y.com"}).status_code == 422


def test_resend_verification_has_cooldown(client, outbox):
    from app import ratelimit

    r = client.post("/api/auth/register", json={"name": "Fatou", "email": "fatou@example.org", "password": "motdepasse1", **TERMS})
    h = session_headers(client, r)
    assert client.post("/api/auth/verification/envoyer", headers=h).status_code == 429  # e-mail parti à l'inscription
    ratelimit.reset("resend-1min:")
    assert client.post("/api/auth/verification/envoyer", headers=h).json()["sent"] is True
    assert len(outbox) == 2


def test_name_is_optional_for_api_and_falls_back(client):
    r = client.post("/api/auth/register", json={"email": "sans.nom@example.org", "password": "motdepasse1", **TERMS})
    h = session_headers(client, r)
    assert client.get("/api/auth/me", headers=h).json()["display_name"] == "sans.nom"
    bad = client.post("/api/auth/register", json={"name": "<b>", "email": "bad@example.org", "password": "motdepasse1", **TERMS})
    assert bad.status_code == 422


def test_forgot_and_reset_password(client, outbox):
    from app.security import VERIFY_EMAIL

    client.post("/api/auth/register", json={"name": "Yao", "email": "yao@example.org", "password": "motdepasse1", **TERMS})
    client.cookies.clear()
    outbox.clear()
    # même réponse pour une adresse inconnue, et aucun e-mail
    assert client.post("/api/auth/mot-de-passe-oublie", json={"email": "inconnu@example.org"}).json()["sent"] is True
    assert outbox == []
    assert client.post("/api/auth/mot-de-passe-oublie", json={"email": "Yao@Example.org"}).json()["sent"] is True
    assert len(outbox) == 1 and "Yao" in outbox[0]["text"]
    token = _link(outbox[0], "/reinitialiser")
    assert client.post("/api/auth/reinitialiser", json={"token": token, "password": "faible"}).status_code == 422
    r = client.post("/api/auth/reinitialiser", json={"token": token, "password": "nouveau2026"})
    assert r.status_code == 200 and r.json()["home"] == "/mes-bourses"
    assert "httponly" in r.headers["set-cookie"].lower()  # ce navigateur reste connecté, par cookie
    client.cookies.clear()
    # le lien ne sert qu'une fois
    assert client.post("/api/auth/reinitialiser", json={"token": token, "password": "encore2026x"}).status_code == 400
    assert client.post("/api/auth/login", json={"email": "yao@example.org", "password": "motdepasse1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "yao@example.org", "password": "nouveau2026"}).status_code == 200
    client.cookies.clear()
    # un lien de confirmation ne remplace pas un lien de réinitialisation
    from app.db import SessionLocal
    from app.models import User
    from app.security import create_link_token
    from sqlalchemy import select

    db = SessionLocal()
    try:
        verify = create_link_token(db.scalars(select(User).where(User.email == "yao@example.org")).first(), VERIFY_EMAIL, 10)
    finally:
        db.close()
    assert client.post("/api/auth/reinitialiser", json={"token": verify, "password": "encore2026x"}).status_code == 400


def test_mailer_console_fallback(capsys):
    from app.mailer import send_mail, verification_email

    subject, text, html = verification_email("Awa", "http://localhost:3000/verifier-email?token=abc", 48)
    assert send_mail("awa@example.org", subject, text, html) is True
    out = capsys.readouterr().out
    assert "http://localhost:3000/verifier-email?token=abc" in out and "Confirmez votre adresse" in out


def test_mailer_console_never_logs_links_in_production(monkeypatch, capsys):
    """En ligne sans moyen d'envoi, le message (et son lien) n'est pas écrit dans les journaux."""
    from app.config import get_settings
    from app.mailer import send_mail

    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert send_mail("awa@example.org", "Sujet", "lien secret : http://x/reinitialiser?token=abc") is False
    assert "token=abc" not in capsys.readouterr().out
