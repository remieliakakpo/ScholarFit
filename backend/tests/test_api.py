from datetime import date

from tests.conftest import login


def test_health(client):
    r = client.get("/api/health")
    assert r.json()["ok"] is True


def test_catalogue_filters(client):
    r = client.get("/api/scholarships", params={"per_page": 100})
    assert r.status_code == 200
    total = r.json()["total"]
    assert total >= 25
    r = client.get("/api/scholarships", params={"level": "BAC7", "per_page": 100})
    assert all("BAC7" in s["levels"] for s in r.json()["items"])
    r = client.get("/api/scholarships", params={"country": "DE", "per_page": 100})
    assert all(not s["study_countries"] or "DE" in s["study_countries"] for s in r.json()["items"])
    r = client.get("/api/scholarships", params={"nationality": "FR", "q": "eiffel"})
    assert r.json()["total"] == 0  # Eiffel exclut les Français


def test_register_profile_minimum_and_matching(client):
    r = client.post("/api/auth/register", json={"email": "nouveau@example.org", "password": "motdepasse1"})
    assert r.status_code == 201
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get("/api/matches", headers=h)
    assert r.json()["minimum_ok"] is False
    assert set(r.json()["missing_minimum"]) == {"nationalité", "âge", "niveau visé", "domaine"}

    r = client.put("/api/profile", headers=h, json={
        "nationalities": ["CM"], "birth_date": str(date(date.today().year - 24, 1, 1)),
        "target_level": "BAC5", "domain": "economie",
    })
    assert r.json()["minimum_ok"] is True
    r = client.get("/api/matches", headers=h)
    data = r.json()
    assert data["minimum_ok"] and data["items"]
    for m in data["items"]:
        assert "BAC5" in m["scholarship"]["levels"]
        assert 0 <= m["score"] <= 100
        assert m["chance"] in ("faible", "moyenne", "bonne")


def test_invalid_profile_values(client, demo):
    assert client.put("/api/profile", headers=demo, json={"target_level": "BAC9"}).status_code == 422
    assert client.put("/api/profile", headers=demo, json={"nationalities": ["XX"]}).status_code == 422


def test_chat_flow_asks_then_answers(client):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Bonjour, je cherche une bourse"}], "criteria": {}})
    out = r.json()
    assert out["results"] == [] and out["missing"]
    crit = out["criteria"]
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Je suis en L3 de biologie au Sénégal, j'ai 22 ans, je veux un master en France ou au Canada"}], "criteria": crit})
    out = r.json()
    assert out["criteria"]["target_level"] == "BAC5"
    assert out["criteria"]["domain"] == "biologie"
    assert out["criteria"]["nationalities"] == ["SN"]
    assert set(out["criteria"]["wished_countries"]) == {"FR", "CA"}
    assert out["results"], out["reply"]
    assert len(out["results"]) <= 3  # visiteur anonyme
    for m in out["results"]:
        assert m["scholarship"]["official_url"].startswith("http")


def test_kanban_and_check(client, demo):
    s = client.get("/api/scholarships", params={"q": "chevening", "include_expired": True}).json()["items"][0]
    r = client.post("/api/applications", headers=demo, json={"scholarship_id": s["id"]})
    assert r.status_code == 201
    app = r.json()
    assert set(app["checklist"]) == set(s["requirements"])
    r = client.patch(f"/api/applications/{app['id']}", headers=demo, json={"status": "envoyee", "checklist": {"lettre": True}})
    assert r.json()["status"] == "envoyee" and r.json()["checklist"]["lettre"] is True
    assert client.patch(f"/api/applications/{app['id']}", headers=demo, json={"status": "bof"}).status_code == 422
    r = client.get(f"/api/applications/{app['id']}/check", headers=demo)
    assert r.status_code == 200 and r.json()["ok"] is False


def test_admin_rights(client, demo, admin):
    body = {"title": "Bourse test locale", "organization": "Mairie de Test", "official_url": "https://example.org/b",
            "levels": ["BAC3"], "domains": ["tous"]}
    assert client.post("/api/admin/scholarships", headers=demo, json=body).status_code == 403
    r = client.post("/api/admin/scholarships", headers=admin, json=body)
    assert r.status_code == 201 and r.json()["verified_at"]
    assert client.get("/api/admin/sources", headers=admin).status_code == 200
    r = client.post("/api/admin/maintenance", headers=admin)
    assert r.status_code == 200


def test_delete_account(client):
    r = client.post("/api/auth/register", json={"email": "efface@example.org", "password": "motdepasse1"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.delete("/api/auth/me", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
