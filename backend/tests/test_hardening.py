"""Audit de sécurité : liens, adresses internes (SSRF), tailles, fichiers piégés, droits d'accès."""
import io
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.netguard import BlockedAddress, http_url, is_public_ip, safe_client
from tests.conftest import login, register


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "data:text/html,<script>x</script>", "ftp://exemple.org/a",
                                 "http://", "  JAVASCRIPT:alert(1)", "https://exemple.org/\r\nSet-Cookie: x"])
def test_only_http_links(bad):
    with pytest.raises(ValueError):
        http_url(bad)


def test_http_links_accepted():
    assert http_url(" https://www.campusfrance.org/fr ") == "https://www.campusfrance.org/fr"
    assert http_url("") is None and http_url(None) is None


def test_internal_addresses_are_not_public():
    for ip in ("127.0.0.1", "10.0.0.5", "172.18.0.3", "192.168.1.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "0.0.0.0"):
        assert not is_public_ip(ip), ip
    assert is_public_ip("8.8.8.8")


def test_fetcher_refuses_internal_addresses():
    """La collecte ne peut pas faire interroger par le serveur une adresse interne (SSRF)."""
    with safe_client(timeout=2) as c:
        for url in ("http://127.0.0.1:8000/api/health", "http://localhost/", "http://169.254.169.254/latest/meta-data/"):
            with pytest.raises(BlockedAddress):
                c.get(url)


def test_redirect_to_internal_address_is_blocked():
    """Une page publique qui redirige vers une adresse interne est aussi bloquée."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/api/health"})

    from app.netguard import guard_request

    with httpx.Client(transport=httpx.MockTransport(handler), event_hooks={"request": [guard_request]}, follow_redirects=True) as c:
        with pytest.raises(BlockedAddress):
            c.get("http://8.8.8.8/page")


def test_upsert_refuses_javascript_link(client):
    from app.db import SessionLocal
    from app.scrapers.collector import upsert

    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            upsert(db, {"title": "Bourse piégée", "organization": "X", "official_url": "javascript:alert(document.cookie)"}, None)
        s, _ = upsert(db, {"title": "Bourse au lien de candidature piégé", "organization": "X", "official_url": "https://exemple.org/b",
                           "apply_url": "javascript:alert(1)"}, None)
        assert s.apply_url is None
        db.rollback()
    finally:
        db.close()


def test_admin_cannot_save_javascript_link(client, admin):
    body = {"title": "Bourse test", "organization": "Org", "official_url": "javascript:alert(1)", "levels": ["BAC5"]}
    assert client.post("/api/admin/scholarships", headers=admin, json=body).status_code == 422


def test_meeting_link_must_be_http(client):
    from app.db import SessionLocal
    from app.models import Advisor, Coaching, User

    student = register(client, "rdv@example.org")
    db = SessionLocal()
    try:
        sid = db.query(User).filter_by(email="rdv@example.org").one().id
        adv = db.query(Advisor).join(User).filter(User.email == "conseiller@example.org").one()
        c = Coaching(student_id=sid, advisor_id=adv.id, goal="Bourse de master au Canada", status="en_cours", share_consent=True)
        db.add(c)
        db.commit()
        cid = c.id
    finally:
        db.close()
    when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    bad = client.post(f"/api/accompagnement/{cid}/rendez-vous", headers=student, json={"starts_at": when, "link": "javascript:alert(1)"})
    assert bad.status_code == 422
    ok = client.post(f"/api/accompagnement/{cid}/rendez-vous", headers=student, json={"starts_at": when, "link": "https://meet.example.org/abc"})
    assert ok.status_code == 201, ok.text

    # Un conseiller désactivé perd aussitôt l'accès au dossier du candidat
    advisor = login(client, "conseiller@example.org", "conseil12345")
    assert client.get(f"/api/accompagnement/{cid}", headers=advisor).status_code == 200
    db = SessionLocal()
    try:
        a = db.query(Advisor).join(User).filter(User.email == "conseiller@example.org").one()
        a.active = False
        db.commit()
        assert client.get(f"/api/accompagnement/{cid}", headers=advisor).status_code == 404
        assert client.get("/api/accompagnement/conseiller", headers=advisor).status_code == 403
        a.active = True
        db.commit()
    finally:
        db.close()


def test_request_size_limits(client, demo):
    big = {"messages": [{"role": "user", "content": "x" * 4001}], "criteria": {}}
    assert client.post("/api/chat", json=big).status_code == 422
    many = {"messages": [{"role": "user", "content": "bonjour"}] * 61, "criteria": {}}
    assert client.post("/api/chat", json=many).status_code == 422
    huge = client.put("/api/profile", headers={**demo, "Content-Type": "application/json"}, content=b'{"city": "' + b"x" * 1_200_000 + b'"}')
    assert huge.status_code == 413


def test_docx_bomb_rejected():
    from app.ai.documents import extract_text

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"0" * (31 * 1024 * 1024))  # quelques Ko compressés, 31 Mo décompressés
    with pytest.raises(ValueError):
        extract_text("cv.docx", buf.getvalue())


def test_cv_error_does_not_leak_details(client, demo):
    r = client.post("/api/profile/cv", headers=demo, files={"file": ("cv.pdf", b"%PDF-pas-un-vrai-pdf", "application/pdf")})
    assert r.status_code == 422 and "Essayez un PDF texte" in r.json()["detail"]


def test_ai_needs_confirmed_email(client):
    from app.config import get_settings
    from app.models import User
    from app.quota import can_use_ai

    s = get_settings()
    old = s.anthropic_api_key
    s.anthropic_api_key = "cle-de-test"
    try:
        assert can_use_ai(User(id=999, email="x@example.org", email_verified_at=None), db=None) is False
    finally:
        s.anthropic_api_key = old
