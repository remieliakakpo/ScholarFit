from datetime import date, datetime, timedelta, timezone

from tests.conftest import login


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "motdepasse1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_coaching_flow(client, demo):
    advisor = login(client, "conseiller@example.org", "conseil12345")
    assert client.get("/api/auth/me", headers=advisor).json()["is_advisor"] is True
    assert client.get("/api/auth/me", headers=demo).json()["is_advisor"] is False

    apps = client.get("/api/applications", headers=demo).json()
    body = {"goal": "Obtenir une bourse de master en France", "needs": ["lettre", "entretien"],
            "application_ids": [apps[0]["id"]], "share_consent": False}
    assert client.post("/api/accompagnement", headers=demo, json=body).status_code == 422  # accord obligatoire
    body["share_consent"] = True
    r = client.post("/api/accompagnement", headers=demo, json=body)
    assert r.status_code == 201, r.text
    c = r.json()
    # attribution automatique au conseiller de démo (français, master, informatique, France)
    assert c["status"] == "en_cours" and c["advisor"]["display_name"] == "Moussa Ndiaye"
    assert client.post("/api/accompagnement", headers=demo, json=body).status_code == 409  # un seul à la fois

    d = client.get(f"/api/accompagnement/{c['id']}", headers=demo).json()
    titles = [s["title"] for s in d["steps"]]
    assert "Préparer l'entretien" in titles and "Faire relire votre lettre de motivation" in titles
    dues = [s["due_date"] for s in d["steps"]]
    assert dues == sorted(dues) and min(dues) > str(date.today())
    assert d["student"] is None and len(d["applications"]) == 1  # le candidat ne se voit pas « résumé »

    # le conseiller voit le dossier, le candidat qui n'est pas concerné ne voit rien
    a = client.get(f"/api/accompagnement/{c['id']}", headers=advisor).json()
    assert a["my_role"] == "conseiller" and a["student"]["full_name"] == "Awa Diop"
    other = _register(client, "curieux@example.org")
    assert client.get(f"/api/accompagnement/{c['id']}", headers=other).status_code == 404
    assert client.get("/api/accompagnement/conseiller", headers=other).status_code == 403

    # messages + non lus + alerte
    r = client.post(f"/api/accompagnement/{c['id']}/messages", headers=advisor, json={"content": "Bonjour Awa, envoie-moi ta lettre."})
    assert r.status_code == 201
    assert client.get("/api/accompagnement", headers=demo).json()[0]["unread"] == 1
    d = client.get(f"/api/accompagnement/{c['id']}", headers=demo).json()
    assert d["messages"][-1]["author_name"] == "Moussa Ndiaye" and d["unread"] == 0
    assert any(al["kind"] == "accompagnement" and "Moussa" in al["message"] for al in client.get("/api/alerts", headers=demo).json())

    # étapes : le candidat coche, ne modifie pas ; le conseiller ajoute
    step = d["steps"][0]
    assert client.patch(f"/api/accompagnement/etapes/{step['id']}", headers=demo, json={"done": True}).json()["done"] is True
    assert client.patch(f"/api/accompagnement/etapes/{step['id']}", headers=demo, json={"title": "Autre"}).status_code == 403
    r = client.post(f"/api/accompagnement/{c['id']}/etapes", headers=advisor, json={"title": "Traduire les relevés de notes"})
    assert r.status_code == 201
    assert client.get("/api/accompagnement", headers=demo).json()[0]["progress"] > 0

    # rendez-vous : proposé par le conseiller, confirmé par le candidat
    when = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
    m = client.post(f"/api/accompagnement/{c['id']}/rendez-vous", headers=advisor, json={"starts_at": when, "topic": "Lancement"}).json()
    assert m["status"] == "propose"
    assert client.patch(f"/api/accompagnement/rendez-vous/{m['id']}", headers=advisor, json={"status": "confirme"}).status_code == 403
    assert client.patch(f"/api/accompagnement/rendez-vous/{m['id']}", headers=demo, json={"status": "confirme"}).json()["status"] == "confirme"
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.post(f"/api/accompagnement/{c['id']}/rendez-vous", headers=demo, json={"starts_at": past}).status_code == 422

    # fin et avis
    assert client.post(f"/api/accompagnement/{c['id']}/avis", headers=demo, json={"rating": 5}).status_code == 409
    assert client.post(f"/api/accompagnement/{c['id']}/terminer", headers=demo, json={}).status_code == 403
    assert client.post(f"/api/accompagnement/{c['id']}/terminer", headers=advisor, json={"note": "Bravo !"}).json()["status"] == "termine"
    assert client.post(f"/api/accompagnement/{c['id']}/messages", headers=demo, json={"content": "merci"}).status_code == 409
    assert client.post(f"/api/accompagnement/{c['id']}/avis", headers=demo, json={"rating": 5, "feedback": "Top"}).json()["rating"] == 5


def test_admin_assigns_when_no_advisor_fits(client, admin):
    # le conseiller de démo est mis en pause : la demande attend l'administration
    advisors = client.get("/api/admin/conseillers", headers=admin).json()
    demo_adv = next(a for a in advisors if a["email"] == "conseiller@example.org")
    client.patch(f"/api/admin/conseillers/{demo_adv['id']}", headers=admin, json={"active": False})

    student = _register(client, "candidate2@example.org")
    r = client.post("/api/accompagnement", headers=student, json={"goal": "Trouver une bourse de doctorat au Canada", "share_consent": True})
    c = r.json()
    assert c["status"] == "demande" and c["advisor"] is None
    assert any("demande d'accompagnement" in al["message"] for al in client.get("/api/alerts", headers=admin).json())
    assert client.post(f"/api/accompagnement/{c['id']}/rendez-vous", headers=student,
                       json={"starts_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}).status_code == 409

    # nouveau conseiller, puis attribution manuelle
    _register(client, "mentor2@example.org")
    assert client.post("/api/admin/conseillers", headers=admin, json={"email": "inconnu@example.org", "display_name": "X Y"}).status_code == 404
    adv = client.post("/api/admin/conseillers", headers=admin, json={"email": "mentor2@example.org", "display_name": "Claire Martin", "countries": ["CA"]}).json()
    pending = client.get("/api/admin/accompagnement", headers=admin, params={"status": "demande"}).json()
    item = next(p for p in pending if p["id"] == c["id"])
    assert item["suggestions"][0]["id"] == adv["id"]
    r = client.post(f"/api/admin/accompagnement/{c['id']}/attribuer", headers=admin, json={"advisor_id": adv["id"]})
    assert r.json()["status"] == "en_cours" and r.json()["advisor"]["display_name"] == "Claire Martin"
    mentor = login(client, "mentor2@example.org", "motdepasse1")
    assert [x["id"] for x in client.get("/api/accompagnement/conseiller", headers=mentor).json()] == [c["id"]]

    # le candidat peut arrêter ; l'admin ne peut plus attribuer
    assert client.post(f"/api/accompagnement/{c['id']}/annuler", headers=student).json()["status"] == "annule"
    assert client.post(f"/api/admin/accompagnement/{c['id']}/attribuer", headers=admin, json={"advisor_id": adv["id"]}).status_code == 409
    client.patch(f"/api/admin/conseillers/{demo_adv['id']}", headers=admin, json={"active": True})


def test_coaching_reminders(client):
    from app.coaching import run_reminders
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        assert run_reminders(db, today=date.today()) >= 0
    finally:
        db.close()
