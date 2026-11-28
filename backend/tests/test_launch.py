"""Lancement : paiement en ligne (simulation et CinetPay simulé), e-mails, rappels, pages pays,
documents d'accompagnement et retrait des offres au lien cassé."""
from datetime import date, timedelta

from sqlalchemy import select

from tests.conftest import login, register


def _register(client, email):
    return register(client, email)


def _db():
    from app.db import SessionLocal

    return SessionLocal()


# ------------------------------------------------------------------ paiement
def test_payment_config_defaults_to_simulation(client):
    c = client.get("/api/payments/config").json()
    assert c["online"] is True and c["provider"] == "simulation" and c["test_mode"] is True


def test_subscription_paid_online_opens_subscription(client):
    h = _register(client, "abonne-en-ligne@example.org")
    before = client.get("/api/credits", headers=h).json()
    assert before["subscription"]["active"] is False

    r = client.post("/api/payments/checkout", headers=h, json={"purpose": "abonnement"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["amount"] == 2500 and p["status"] == "en_attente" and "/paiement/simulation?tx=" in p["checkout_url"]

    # un autre compte ne peut ni voir ni confirmer ce paiement
    other = _register(client, "voisin-paiement@example.org")
    assert client.get(f"/api/payments/{p['transaction_id']}", headers=other).status_code == 404

    r = client.post(f"/api/payments/{p['transaction_id']}/simulate", headers=h, json={"outcome": "paye"})
    assert r.status_code == 200 and r.json()["status"] == "paye"
    after = client.get("/api/credits", headers=h).json()
    assert after["subscription"]["active"] is True and after["subscription"]["left_this_period"] == 10

    # confirmer deux fois n'ouvre pas deux mois
    client.post(f"/api/payments/{p['transaction_id']}/simulate", headers=h, json={"outcome": "paye"})
    assert client.get("/api/credits", headers=h).json()["paid_total"] == 1

    from app.models import EmailLog
    db = _db()
    try:
        mails = db.scalars(select(EmailLog).where(EmailLog.to == "abonne-en-ligne@example.org", EmailLog.kind == "paiement")).all()
        assert len(mails) == 1 and mails[0].status == "envoye"
    finally:
        db.close()


def test_cancelled_test_payment_grants_nothing(client):
    h = _register(client, "annule-paiement@example.org")
    p = client.post("/api/payments/checkout", headers=h, json={"purpose": "abonnement"}).json()
    r = client.post(f"/api/payments/{p['transaction_id']}/simulate", headers=h, json={"outcome": "annule"})
    assert r.json()["status"] == "annule"
    assert client.get("/api/credits", headers=h).json()["subscription"]["active"] is False


def test_coaching_paid_online(client):
    h = _register(client, "coaching-paye@example.org")
    body = {"goal": "Master en France", "needs": ["lettre"], "application_ids": [], "share_consent": True, "offer": "premium"}
    r = client.post("/api/accompagnement", headers=h, json=body)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["payment_status"] == "a_payer"
    p = client.post("/api/payments/checkout", headers=h, json={"purpose": "accompagnement", "coaching_id": c["id"]}).json()
    assert p["amount"] == 35000
    client.post(f"/api/payments/{p['transaction_id']}/simulate", headers=h, json={"outcome": "paye"})
    assert client.get(f"/api/accompagnement/{c['id']}", headers=h).json()["payment_status"] == "paye"
    # déjà réglé : plus de nouveau paiement possible
    assert client.post("/api/payments/checkout", headers=h, json={"purpose": "accompagnement", "coaching_id": c["id"]}).status_code == 409
    # on ne paie pas l'accompagnement de quelqu'un d'autre
    other = _register(client, "pas-le-mien@example.org")
    assert client.post("/api/payments/checkout", headers=other, json={"purpose": "accompagnement", "coaching_id": c["id"]}).status_code == 404


def test_cinetpay_flow_with_mocked_api(client, admin, monkeypatch):
    """CinetPay : initialisation, notification, vérification du statut auprès de l'API (jamais la notification seule)."""
    from app import payments
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "payment_provider", "cinetpay")
    monkeypatch.setattr(s, "cinetpay_apikey", "cle")
    monkeypatch.setattr(s, "cinetpay_site_id", "123")
    monkeypatch.setattr(s, "cinetpay_secret_key", "")
    calls = {"check": "WAITING_FOR_CUSTOMER"}

    class R:
        def __init__(self, data):
            self._d = data

        def json(self):
            return self._d

    def fake_post(url, json=None, timeout=None, **_):
        if url.endswith("/payment"):
            assert json["amount"] == 2500 and json["currency"] == "XOF" and json["notify_url"].endswith("/api/payments/cinetpay/notify")
            return R({"code": "201", "message": "CREATED", "data": {"payment_url": "https://checkout.cinetpay.com/payment/abc"}})
        status = calls["check"]
        return R({"code": "00" if status == "ACCEPTED" else "662", "message": "SUCCES" if status == "ACCEPTED" else "WAITING",
                  "data": {"status": status, "amount": "2500", "currency": "XOF", "payment_method": "FLOOZ", "operator_id": "OP1"}})

    monkeypatch.setattr(payments.httpx, "post", fake_post)
    h = _register(client, "cinetpay@example.org")
    p = client.post("/api/payments/checkout", headers=h, json={"purpose": "abonnement"}).json()
    assert p["checkout_url"] == "https://checkout.cinetpay.com/payment/abc"
    tx = p["transaction_id"]

    # CinetPay teste l'adresse en GET
    assert client.get("/api/payments/cinetpay/notify").status_code == 200
    # notification alors que le client n'a pas encore payé : rien n'est accordé
    client.post("/api/payments/cinetpay/notify", data={"cpm_trans_id": tx, "cpm_site_id": "123"})
    assert client.get(f"/api/payments/{tx}", headers=h).json()["status"] == "en_attente"

    calls["check"] = "ACCEPTED"
    client.post("/api/payments/cinetpay/notify", data={"cpm_trans_id": tx, "cpm_site_id": "123"})
    out = client.get(f"/api/payments/{tx}", headers=h).json()
    assert out["status"] == "paye" and out["method"] == "FLOOZ"
    assert client.get("/api/credits", headers=h).json()["subscription"]["active"] is True

    # retour du candidat (POST de CinetPay) : redirection vers la page du site
    r = client.post("/api/payments/cinetpay/return", data={"transaction_id": tx}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith(f"/paiement/retour?tx={tx}")

    # signature x-token exigée quand la clé secrète est renseignée
    monkeypatch.setattr(s, "cinetpay_secret_key", "secret")
    assert client.post("/api/payments/cinetpay/notify", data={"cpm_trans_id": tx}).status_code == 401

    adm = client.get("/api/admin/payments", headers=admin).json()
    assert adm["totals"]["all_time"] >= 2500 and any(i["transaction_id"] == tx for i in adm["items"])


def test_cinetpay_underpaid_is_refused(client, monkeypatch):
    from app import payments
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "payment_provider", "cinetpay")
    monkeypatch.setattr(s, "cinetpay_apikey", "cle")
    monkeypatch.setattr(s, "cinetpay_site_id", "123")

    class R:
        def __init__(self, d):
            self._d = d

        def json(self):
            return self._d

    def fake_post(url, json=None, timeout=None, **_):
        if url.endswith("/payment"):
            return R({"code": "201", "data": {"payment_url": "https://checkout.cinetpay.com/x"}})
        return R({"code": "00", "message": "SUCCES", "data": {"status": "ACCEPTED", "amount": "100", "currency": "XOF"}})

    monkeypatch.setattr(payments.httpx, "post", fake_post)
    h = _register(client, "radin@example.org")
    tx = client.post("/api/payments/checkout", headers=h, json={"purpose": "abonnement"}).json()["transaction_id"]
    assert client.get(f"/api/payments/{tx}", headers=h).json()["status"] == "echoue"
    assert client.get("/api/credits", headers=h).json()["subscription"]["active"] is False


# ------------------------------------------------------------------ e-mails et rappels
def test_mailer_renders_and_dedupes(client):
    from app.mailer import email_button, render_html, send_email
    from app.models import EmailLog

    html = render_html("Objet <test>", "Bonjour,\n\nLigne", email_button("Ouvrir", "/suivi"))
    assert "Objet &lt;test&gt;" in html and "http://localhost:3000/suivi" in html and "Scholar" in html
    db = _db()
    try:
        assert send_email(db, "x@example.org", "Sujet", "Texte", key="unique-1") is True
        db.commit()
        assert send_email(db, "x@example.org", "Sujet", "Texte", key="unique-1") is False
        assert len(db.scalars(select(EmailLog).where(EmailLog.key == "unique-1")).all()) == 1
    finally:
        db.close()


def test_deadline_reminder_emails(client):
    from app.alerts import run_alerts
    from app.models import Application, EmailLog, Scholarship, User

    h = _register(client, "rappel@example.org")
    db = _db()
    try:
        s = db.scalars(select(Scholarship).where(Scholarship.deadline.is_not(None))).first()
        user = db.scalars(select(User).where(User.email == "rappel@example.org")).one()
        db.add(Application(user_id=user.id, scholarship_id=s.id, status="a_preparer"))
        db.commit()
        today = s.deadline - timedelta(days=5)  # palier J-7 atteint
        run_alerts(db, today=today)
        run_alerts(db, today=today + timedelta(days=1))  # même palier : pas de second e-mail
        mails = db.scalars(select(EmailLog).where(EmailLog.to == "rappel@example.org", EmailLog.kind == "rappel")).all()
        assert len(mails) == 1 and mails[0].key == f"rappel-{s.id}-J7-u{user.id}"
        run_alerts(db, today=s.deadline - timedelta(days=1))
        mails = db.scalars(select(EmailLog).where(EmailLog.to == "rappel@example.org", EmailLog.kind == "rappel")).all()
        assert len(mails) == 2
    finally:
        db.close()
    assert h


# ------------------------------------------------------------------ référencement et qualité des données
def test_seo_destinations(client):
    rows = client.get("/api/seo/destinations").json()
    assert rows and all(r["slug"] and r["total"] > 0 for r in rows)
    fr = next(r for r in rows if r["code"] == "FR")
    assert fr["slug"] == "france"
    d = client.get("/api/seo/destinations/france").json()
    assert d["code"] == "FR" and d["total"] == fr["total"]
    b = client.get("/api/seo/destinations/france?kind=bourses").json()
    assert all(i["kind"] == "bourse" for i in b["items"]) and b["total"] == fr["counts"]["bourse"]
    assert client.get("/api/seo/destinations/atlantide").status_code == 404
    assert client.get("/api/seo/destinations/france?lang=en").json()["name"] == "France"


def test_broken_links_hidden_from_public(client):
    from app.models import Scholarship

    db = _db()
    try:
        s = db.scalars(select(Scholarship).where(Scholarship.deadline >= date.today(), Scholarship.review == "publie",
                                                 Scholarship.link_status != "casse", Scholarship.kind == "bourse")).first()
        before = client.get("/api/scholarships", params={"q": s.title, "per_page": 100, "kind": s.kind}).json()["total"]
        s.link_status = "casse"
        db.commit()
        after = client.get("/api/scholarships", params={"q": s.title, "per_page": 100, "kind": s.kind}).json()["total"]
        assert after == before - 1
        s.link_status = "ok"
        db.commit()
    finally:
        db.close()


# ------------------------------------------------------------------ documents d'accompagnement
def test_coaching_files(client):
    from tests.conftest import login as _login

    h = _register(client, "pieces@example.org")
    body = {"goal": "Licence au Canada", "needs": ["cv"], "application_ids": [], "share_consent": True, "offer": "standard"}
    c = client.post("/api/accompagnement", headers=h, json=body).json()
    pdf = b"%PDF-1.4 test"
    r = client.post(f"/api/accompagnement/{c['id']}/fichiers", headers=h, files={"file": ("releves.pdf", pdf, "application/pdf")},
                    data={"category": "piece"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    # le candidat ne livre pas de « livrable »
    assert client.post(f"/api/accompagnement/{c['id']}/fichiers", headers=h, files={"file": ("cv.pdf", pdf, "application/pdf")},
                       data={"category": "livrable"}).status_code == 403
    assert client.post(f"/api/accompagnement/{c['id']}/fichiers", headers=h, files={"file": ("x.exe", b"MZ", "application/x-msdownload")},
                       data={"category": "piece"}).status_code == 415
    d = client.get(f"/api/accompagnement/{c['id']}", headers=h).json()
    assert d["files"][0]["filename"] == "releves.pdf" and d["files"][0]["mine"] is True
    got = client.get(f"/api/accompagnement/{c['id']}/fichiers/{fid}", headers=h)
    assert got.status_code == 200 and got.content == pdf
    stranger = _register(client, "etranger-fichiers@example.org")
    assert client.get(f"/api/accompagnement/{c['id']}/fichiers/{fid}", headers=stranger).status_code == 404
    assert client.delete(f"/api/accompagnement/{c['id']}/fichiers/{fid}", headers=h).status_code == 204
    adv = c.get("advisor")
    if adv:  # l'expert attribué peut livrer
        a = _login(client, "conseiller@example.org", "conseil12345")
        client.post(f"/api/accompagnement/{c['id']}/annuler", headers=h)
        assert a


def test_coaching_files_checked_by_content_and_large_ones_allowed(client):
    """Le type annoncé doit correspondre au contenu ; un document de quelques Mo passe le garde-fou de taille."""
    h = _register(client, "pieces-controle@example.org")
    body = {"goal": "Master en France", "needs": ["cv"], "application_ids": [], "share_consent": True, "offer": "standard"}
    c = client.post("/api/accompagnement", headers=h, json=body).json()
    url = f"/api/accompagnement/{c['id']}/fichiers"
    fake = client.post(url, headers=h, files={"file": ("releves.pdf", b"<html>pas un pdf</html>", "application/pdf")},
                       data={"category": "piece"})
    assert fake.status_code == 415
    big = b"%PDF-1.4\n" + b"0" * (3 * 1024 * 1024)
    r = client.post(url, headers=h, files={"file": ("diplome.pdf", big, "application/pdf")}, data={"category": "piece"})
    assert r.status_code == 201, r.text
