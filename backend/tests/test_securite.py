"""Lot sécurité : production, comptes de démo, clé, paiement, droits admin, sessions, fiches éditées, limites."""
import pytest
from sqlalchemy import select

from app import security
from app.config import get_settings
from app.db import SessionLocal
from app.models import Scholarship, User
from tests.conftest import login, session_headers

TERMS = {"accept_terms": True}


def test_production_blocks_demo_simulation_and_dev_key(client, monkeypatch):
    from app import payments
    from app.demo import ensure_demo_accounts

    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    assert s.is_production and not s.demo_enabled
    assert payments.provider() == "manuel"  # jamais de faux guichet en ligne
    with pytest.raises(RuntimeError, match="SECRET_KEY"):  # clé de développement refusée en ligne
        s.check_production()
    db = SessionLocal()
    try:
        ensure_demo_accounts(db)
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"email": "admin@example.org", "password": "admin12345"})
    assert r.status_code == 401
    # retour en mode local : les comptes de démo sont réparés pour les autres tests
    monkeypatch.setattr(s, "app_env", "dev")
    db = SessionLocal()
    try:
        ensure_demo_accounts(db)
    finally:
        db.close()
    assert login(client, "admin@example.org", "admin12345")


def test_admin_only_after_email_confirmation(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "admin_emails", "admin@example.org,chef@gmail.com")
    r = client.post("/api/auth/register", json={"email": "chef@gmail.com", "password": "Chef2026x", "name": "Chef", **TERMS})
    h = session_headers(client, r)
    assert client.get("/api/admin/sources", headers=h).status_code == 403
    db = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "chef@gmail.com")).first()
        token = security.create_link_token(u, security.VERIFY_EMAIL, 60)
    finally:
        db.close()
    assert client.post("/api/auth/verification", json={"token": token}).status_code == 200
    assert client.get("/api/admin/sources", headers=h).status_code == 200


def test_password_reset_closes_other_sessions(client):
    r = client.post("/api/auth/register", json={"email": "sessions@gmail.com", "password": "Session2026x", "name": "Sam", **TERMS})
    old = session_headers(client, r)
    assert client.get("/api/auth/me", headers=old).status_code == 200
    db = SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "sessions@gmail.com")).first()
        token = security.create_link_token(u, security.RESET_PASSWORD, 60)
    finally:
        db.close()
    r = client.post("/api/auth/reinitialiser", json={"token": token, "password": "Nouveau2026x"})
    new = session_headers(client, r)
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=new).status_code == 200


def test_seed_keeps_admin_corrections(client, admin):
    from app.scrapers.collector import run_source

    s = client.get("/api/scholarships/bourse-d-excellence-eiffel").json()
    body = {k: s[k] for k in ("kind", "title", "organization", "official_url", "summary", "levels", "study_countries",
                              "eligible_nationalities", "domains", "languages", "currency", "amount_period", "coverage")}
    body["amount"] = 1400
    assert client.put(f"/api/admin/scholarships/{s['id']}", headers=admin, json=body).status_code == 200
    db = SessionLocal()
    try:
        run_source(db, "Données d'exemple")
        db.commit()
        assert db.get(Scholarship, s["id"]).amount == 1400
    finally:
        db.close()


def test_login_rate_limit(client):
    """Cinq erreurs sur un même compte : pause de 15 minutes (voir aussi test_security)."""
    codes = [client.post("/api/auth/login", json={"email": "x@gmail.com", "password": "faux12345"}).status_code
             for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
