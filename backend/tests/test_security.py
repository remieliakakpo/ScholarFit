"""Sécurité des comptes : cookie de session, CSRF, limitation des tentatives, vérification de
l'adresse, mot de passe oublié, révocation, consentement et export des données."""
import time
from types import SimpleNamespace

import jwt
import pytest

from app import ratelimit
from app.config import DEV_SECRET, Settings, get_settings
from tests.conftest import login, register, session_headers


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("app.routers.auth.send_mail", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _link_token(mail_body: str) -> str:
    return mail_body.split("token=")[1].split()[0]


def test_session_cookie_is_httponly_and_not_in_body(client, outbox):
    r = client.post("/api/auth/register", json={"email": "cookie@example.org", "password": "motdepasse1", "accept_terms": True})
    assert r.status_code == 201
    assert "access_token" not in r.json() and r.json()["email_verified"] is False
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert len(outbox) == 1 and "/verifier-email?token=" in outbox[0][2]


def test_register_requires_terms(client):
    r = client.post("/api/auth/register", json={"email": "sansaccord@example.org", "password": "motdepasse1"})
    assert r.status_code == 422 and "conditions" in r.json()["detail"]


def test_csrf_header_required_for_changes(client, demo):
    r = client.put("/api/profile", headers={**demo, "X-Requested-With": ""}, json={"city": "Dakar"})
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]
    assert client.get("/api/profile", headers={**demo, "X-Requested-With": ""}).status_code == 200  # lecture : permise


def test_login_locked_after_five_failures(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "demo@example.org", "password": "mauvais1"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "demo@example.org", "password": "demo12345"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    ratelimit.reset()
    assert client.post("/api/auth/login", json={"email": "demo@example.org", "password": "demo12345"}).status_code == 200


def test_register_rate_limited_per_ip(client, outbox):
    codes = [client.post("/api/auth/register", json={"email": f"rafale{i}@example.org", "password": "motdepasse1", "accept_terms": True}).status_code
             for i in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_email_verification_and_admin_only_after_proof(client, outbox):
    s = get_settings()
    old = s.admin_emails
    s.admin_emails = old + ",chef@example.org"
    try:
        r = client.post("/api/auth/register", json={"email": "chef@example.org", "password": "motdepasse1", "accept_terms": True})
        h = session_headers(client, r)
        assert client.get("/api/auth/me", headers=h).json()["is_admin"] is False  # adresse pas encore prouvée
        assert client.post("/api/credits/orders", headers=h, json={"method": "flooz", "reference": "TX1"}).status_code == 403
        token = _link_token(outbox[-1][2])
        assert client.post("/api/auth/verifier-email", json={"token": "faux"}).status_code == 400
        me = client.post("/api/auth/verifier-email", json={"token": token}).json()
        assert me["email_verified"] is True and me["is_admin"] is True
    finally:
        s.admin_emails = old


def test_resend_verification(client, outbox):
    h = register(client, "renvoi@example.org", verify=False)
    outbox.clear()
    assert client.post("/api/auth/renvoyer-verification", headers=h).status_code == 204
    assert len(outbox) == 1


def test_forgot_and_reset_password_revokes_sessions(client, outbox):
    h = register(client, "oubli@example.org")
    unknown = client.post("/api/auth/mot-de-passe-oublie", json={"email": "personne@example.org"})
    known = client.post("/api/auth/mot-de-passe-oublie", json={"email": "oubli@example.org"})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()  # rien ne trahit l'inscription
    reset_mails = [m for m in outbox if m[0] == "oubli@example.org" and "reinitialiser" in m[2]]
    assert len(reset_mails) == 1
    token = _link_token(reset_mails[0][2])
    assert client.post("/api/auth/reinitialiser-mot-de-passe", json={"token": token, "password": "nouveau123"}).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401  # ancienne session révoquée
    assert client.post("/api/auth/reinitialiser-mot-de-passe", json={"token": token, "password": "encore1234"}).status_code == 400  # une seule fois
    assert client.post("/api/auth/login", json={"email": "oubli@example.org", "password": "motdepasse1"}).status_code == 401
    login(client, "oubli@example.org", "nouveau123")


def test_change_password_and_logout(client):
    h = register(client, "change@example.org")
    assert client.post("/api/auth/changer-mot-de-passe", headers=h, json={"current_password": "faux", "new_password": "nouveau123"}).status_code == 400
    r = client.post("/api/auth/changer-mot-de-passe", headers=h, json={"current_password": "motdepasse1", "new_password": "nouveau123"})
    assert r.status_code == 200
    fresh = session_headers(client, r)
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.get("/api/auth/me", headers=fresh).status_code == 200
    out = client.post("/api/auth/logout", headers=fresh)
    assert out.status_code == 204 and "max-age=0" in out.headers["set-cookie"].lower()


def test_sensitive_consent_and_export(client):
    h = register(client, "export@example.org")
    client.put("/api/profile", headers=h, json={"situations": ["refugie"], "city": "Lomé"})
    r = client.get("/api/profile/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["email"] == "export@example.org"
    assert "password_hash" not in data["account"] and "token_version" not in data["account"]
    assert data["profile"]["city"] == "Lomé" and data["profile"]["sensitive_consent_at"]
    client.put("/api/profile", headers=h, json={"situations": []})  # retrait du consentement
    assert client.get("/api/profile/export", headers=h).json()["profile"]["sensitive_consent_at"] is None
    assert client.get("/api/profile/export").status_code == 401


def test_session_renewal_has_a_ceiling():
    from app.security import renewed_session

    s = get_settings()
    now = int(time.time())
    near_end = {"sub": "1", "typ": "session", "ver": 0, "iat": now, "auth": now, "exp": now + 60}
    assert renewed_session(jwt.encode(near_end, s.secret_key, algorithm="HS256"))
    fresh = {**near_end, "exp": now + s.token_expire_minutes * 60}
    assert renewed_session(jwt.encode(fresh, s.secret_key, algorithm="HS256")) is None  # pas encore utile
    too_old = {**near_end, "auth": now - (s.session_max_days + 1) * 86400}
    assert renewed_session(jwt.encode(too_old, s.secret_key, algorithm="HS256")) is None  # il faut se reconnecter


def test_production_refuses_weak_secret():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", secret_key=DEV_SECRET).check_production()
    with pytest.raises(RuntimeError):
        Settings(app_env="production", secret_key="court").check_production()
    Settings(app_env="production", secret_key="x" * 20 + "aléatoire-et-long-0123456789").check_production()
    Settings(app_env="dev", secret_key=DEV_SECRET).check_production()


def test_client_ip_behind_trusted_proxy():
    def req(peer, xff=""):
        return SimpleNamespace(client=SimpleNamespace(host=peer), headers={"x-forwarded-for": xff} if xff else {})

    assert ratelimit.client_ip(req("203.0.113.9", "1.2.3.4")) == "203.0.113.9"  # visiteur direct : en-tête ignoré
    assert ratelimit.client_ip(req("127.0.0.1", "198.51.100.7")) == "198.51.100.7"  # via le site Next.js
    assert ratelimit.client_ip(req("127.0.0.1", "6.6.6.6, 198.51.100.7")) == "198.51.100.7"  # adresse inventée ignorée

    s = get_settings()
    old = s.trusted_proxies
    s.trusted_proxies = "*"  # Docker : le site arrive depuis une adresse du réseau interne
    try:
        assert ratelimit.client_ip(req("172.18.0.3", "6.6.6.6, 198.51.100.7")) == "198.51.100.7"
        assert ratelimit.client_ip(req("172.18.0.3", "198.51.100.7")) == "198.51.100.7"
    finally:
        s.trusted_proxies = old
