"""Alertes par e-mail, recherches sauvegardées, signalements, journal d'audit, calendrier, coûts IA."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tests.conftest import login, register


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("app.mailer.send_mail", lambda to, subject, body, headers=None: sent.append((to, subject, body, headers)) or True)
    return sent


def _db():
    from app.db import SessionLocal

    return SessionLocal()


def _user(db, email):
    from app.models import User

    return db.query(User).filter_by(email=email).one()


# ---------------------------------------------------------------- alertes par e-mail
def test_alerts_grouped_in_one_email_with_unsubscribe(client, outbox):
    from app.alerts import _add, send_alert_emails

    register(client, "alertes@example.org")
    unverified_h = register(client, "pasconfirme@example.org", verify=False)
    assert unverified_h
    db = _db()
    try:
        u, v = _user(db, "alertes@example.org"), _user(db, "pasconfirme@example.org")
        _add(db, u, "test-1", "rappel", "Plus que 7 jour(s) pour « Bourse A ».", None)
        _add(db, u, "test-2", "nouvelle_bourse", "Nouvelle bourse pour vous : « Bourse B ».", 1)
        _add(db, v, "test-3", "rappel", "Plus que 1 jour(s) pour « Bourse C ».", None)
        db.commit()
        assert send_alert_emails(db) >= 1  # d'autres comptes des tests peuvent avoir des alertes en attente
        mine = [m for m in outbox if m[0] == "alertes@example.org"]
        assert len(mine) == 1 and "2 nouvelles alertes" in mine[0][1]
        assert "Bourse A" in mine[0][2] and "Bourse B" in mine[0][2] and "/desabonner?token=" in mine[0][2]
        assert mine[0][3]["List-Unsubscribe"].startswith("<http")
        assert not [m for m in outbox if m[0] == "pasconfirme@example.org"]  # adresse non confirmée : rien
        outbox.clear()
        send_alert_emails(db)
        assert not [m for m in outbox if m[0] == "alertes@example.org"]  # déjà envoyées : pas de doublon
    finally:
        db.close()


def test_unsubscribe_link_turns_off_emails(client, outbox):
    from app.alerts import _add, send_alert_emails, unsubscribe_link

    register(client, "stop@example.org")
    db = _db()
    try:
        u = _user(db, "stop@example.org")
        token = unsubscribe_link(u).split("token=")[1]
    finally:
        db.close()
    assert client.post("/api/alertes/desabonner", json={"token": "faux"}).status_code == 400
    assert client.post("/api/alertes/desabonner", json={"token": token}).status_code == 200
    db = _db()
    try:
        u = _user(db, "stop@example.org")
        assert u.profile.alerts_opt_in is False
        _add(db, u, "apres-desabonnement", "rappel", "Rappel", None)
        db.commit()
        send_alert_emails(db)
        assert not [m for m in outbox if m[0] == "stop@example.org"]
    finally:
        db.close()


def test_new_scholarship_alert_for_profile(client):
    """Corrige un bloc qui ne s'exécutait jamais : les nouvelles bourses du profil créent bien une alerte."""
    from app.alerts import run_alerts
    from app.models import Alert

    db = _db()
    try:
        run_alerts(db)
        demo = _user(db, "demo@example.org")
        kinds = {a.kind for a in db.query(Alert).filter_by(user_id=demo.id)}
        assert "nouvelle_bourse" in kinds
    finally:
        db.close()


# ---------------------------------------------------------------- recherches sauvegardées
def test_saved_search_crud_and_alert(client, admin):
    h = register(client, "recherche@example.org")
    assert client.post("/api/recherches", headers=h, json={"name": "Vide", "filters": {"inconnu": "x"}}).status_code == 422
    r = client.post("/api/recherches", headers=h, json={"name": "Masters en Allemagne", "filters": {"country": "DE", "level": "BAC5"}})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    other = register(client, "curieux2@example.org")
    assert client.delete(f"/api/recherches/{sid}", headers=other).status_code == 404  # pas la sienne
    assert client.patch(f"/api/recherches/{sid}", headers=h, json={"alerts_enabled": True}).json()["alerts_enabled"] is True

    # Une nouvelle fiche qui correspond déclenche une alerte au passage suivant
    new = {"title": "Bourse test Allemagne master", "organization": "DAAD test", "official_url": "https://example.org/daad-test",
           "levels": ["BAC5"], "study_countries": ["DE"], "deadline": str(date.today() + timedelta(days=90))}
    assert client.post("/api/admin/scholarships", headers=admin, json=new).status_code == 201
    from app.alerts import run_alerts
    from app.models import Alert

    db = _db()
    try:
        run_alerts(db)
        u = _user(db, "recherche@example.org")
        msgs = [a.message for a in db.query(Alert).filter_by(user_id=u.id, kind="recherche")]
        assert any("Bourse test Allemagne master" in m and "Masters en Allemagne" in m for m in msgs)
    finally:
        db.close()
    assert client.get("/api/recherches", headers=h).json()[0]["name"] == "Masters en Allemagne"
    assert client.delete(f"/api/recherches/{sid}", headers=h).status_code == 204


# ---------------------------------------------------------------- signalements
def test_report_flow(client, admin):
    sid = client.get("/api/scholarships", params={"per_page": 1}).json()["items"][0]["id"]
    assert client.post(f"/api/scholarships/{sid}/signalements", json={"reason": "lien_mort"}).status_code == 401
    users = [register(client, f"signale{i}@example.org") for i in range(3)]
    assert client.post(f"/api/scholarships/{sid}/signalements", headers=users[0], json={"reason": "inconnu"}).status_code == 422
    for h in users:
        r = client.post(f"/api/scholarships/{sid}/signalements", headers=h, json={"reason": "lien_mort", "comment": "Page 404"})
        assert r.status_code == 201, r.text
    assert client.post(f"/api/scholarships/{sid}/signalements", headers=users[0], json={"reason": "date_fausse"}).status_code == 409
    assert client.get(f"/api/scholarships/{sid}").json()["link_status"] == "casse"  # 3 personnes : lien marqué cassé

    reports = client.get("/api/admin/signalements", headers=admin).json()
    mine = [r for r in reports if r["scholarship"]["id"] == sid]
    assert len(mine) == 3 and mine[0]["open_for_scholarship"] == 3 and mine[0]["reporter"]
    assert client.get("/api/admin/signalements", headers=users[0]).status_code == 403
    r = client.patch(f"/api/admin/signalements/{mine[0]['id']}", headers=admin,
                     json={"status": "corrige", "note": "Nouveau lien", "all_for_scholarship": True})
    assert r.json()["updated"] == 3
    assert not [x for x in client.get("/api/admin/signalements", headers=admin).json() if x["scholarship"]["id"] == sid]
    alerts = client.get("/api/alerts", headers=users[1]).json()
    assert any("a été corrigée" in a["message"] for a in alerts)


# ---------------------------------------------------------------- journal d'audit
def test_admin_actions_are_audited(client, admin):
    new = {"title": "Fiche à supprimer", "organization": "Org", "official_url": "https://example.org/a-supprimer", "levels": ["BAC5"]}
    sid = client.post("/api/admin/scholarships", headers=admin, json=new).json()["id"]
    assert client.delete(f"/api/admin/scholarships/{sid}", headers=admin).status_code == 204
    client.get("/api/admin/sources", headers=admin)  # une lecture n'est pas journalisée
    log = client.get("/api/admin/audit", headers=admin, params={"action": "scholarships"}).json()["items"]
    deleted = next(a for a in log if a["action"] == "DELETE scholarships/{id}" and a["target_id"] == str(sid))
    assert deleted["actor"] == "admin@example.org" and deleted["details"]["titre"] == "Fiche à supprimer"
    assert any(a["action"] == "POST scholarships" for a in log)
    assert not client.get("/api/admin/audit", headers=admin, params={"action": "GET"}).json()["items"]
    all_actions = [a["action"] for a in client.get("/api/admin/audit", headers=admin, params={"per_page": 200}).json()["items"]]
    assert "connexion administrateur" in all_actions
    demo = login(client)
    assert client.get("/api/admin/audit", headers=demo).status_code == 403


def test_password_change_is_audited(client, admin):
    h = register(client, "audit-mdp@example.org")
    client.post("/api/auth/changer-mot-de-passe", headers=h, json={"current_password": "motdepasse1", "new_password": "nouveau123"})
    items = client.get("/api/admin/audit", headers=admin, params={"actor": "audit-mdp@example.org"}).json()["items"]
    assert [a["action"] for a in items] == ["mot de passe changé"]


# ---------------------------------------------------------------- calendrier
def test_ics_export(client):
    items = client.get("/api/scholarships", params={"per_page": 100, "deadline_status": "ouverte,bientot,urgente"}).json()["items"]
    s = next(x for x in items if x.get("deadline"))
    r = client.get(f"/api/scholarships/{s['id']}/calendrier.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" in body and "TRIGGER:-P7D" in body
    assert f"DTSTART;VALUE=DATE:{s['deadline'].replace('-', '')}" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))

    h = register(client, "agenda@example.org")
    client.post("/api/applications", headers=h, json={"scholarship_id": s["id"]})
    mine = client.get("/api/calendrier.ics", headers=h)
    assert mine.status_code == 200 and mine.text.count("BEGIN:VEVENT") == 1
    assert client.get("/api/calendrier.ics").status_code == 401


# ---------------------------------------------------------------- coût de l'IA
def test_ai_cost_recorded_and_budget(client, admin):
    from app.ai import costs
    from app.config import get_settings

    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0, server_tool_use=SimpleNamespace(web_search_requests=3))
    est = costs.estimate(usage)
    s = get_settings()
    assert est["cost_usd"] == pytest.approx(s.ai_price_input_per_mtok + 0.1 * s.ai_price_output_per_mtok + 3 * s.ai_price_per_web_search)
    costs.record(usage, "claude-opus-5-5", "cv")
    data = client.get("/api/admin/couts-ia", headers=admin).json()
    assert data["today"] >= est["cost_usd"] and any(p["purpose"] == "cv" for p in data["by_purpose"])
    old = s.ai_daily_budget_usd
    s.ai_daily_budget_usd = 0.5
    try:
        assert costs.over_budget() is True
    finally:
        s.ai_daily_budget_usd = old
    assert costs.over_budget() is False


def test_ai_cost_purpose_from_caller(monkeypatch):
    from app.ai import client as ai_client

    seen = {}
    monkeypatch.setattr(ai_client.costs, "record", lambda usage, model, purpose: seen.setdefault("purpose", purpose))
    monkeypatch.setattr(ai_client.costs, "over_budget", lambda: False)

    class FakeMessages:
        def create(self, **kw):
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")], usage=None, model=kw["model"])

    monkeypatch.setattr(ai_client, "_get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    assert ai_client.ask_text("s", "u") == "ok"
    assert seen["purpose"] == "test_features"  # module qui a appelé l'IA


# ---------------------------------------------------------------- erreurs du site
def test_client_error_endpoint(client):
    r = client.post("/api/erreurs-site", json={"message": "TypeError: x is undefined", "url": "https://site/bourses/3"})
    assert r.status_code == 204
    assert client.post("/api/erreurs-site", json={"message": "x" * 2000}).status_code == 422


def test_export_contains_saved_searches(client):
    h = register(client, "export2@example.org")
    client.post("/api/recherches", headers=h, json={"name": "Canada", "filters": {"country": "CA"}})
    data = client.get("/api/profile/export", headers=h).json()
    assert data["saved_searches"][0]["name"] == "Canada" and data["reports"] == []


def test_delete_account_detaches_reports_and_audit(client, admin):
    h = register(client, "partant@example.org")
    sid = client.get("/api/scholarships", params={"per_page": 1}).json()["items"][0]["id"]
    client.post(f"/api/scholarships/{sid}/signalements", headers=h, json={"reason": "date_fausse"})
    assert client.delete("/api/auth/me", headers=h).status_code == 204
    reports = client.get("/api/admin/signalements", headers=admin).json()
    assert any(r["scholarship"]["id"] == sid and r["reporter"] is None and r["reason"] == "date_fausse" for r in reports)
    actions = [a["action"] for a in client.get("/api/admin/audit", headers=admin, params={"action": "supprimé"}).json()["items"]]
    assert "compte supprimé par son titulaire" in actions


def _now():
    return datetime.now(timezone.utc)
