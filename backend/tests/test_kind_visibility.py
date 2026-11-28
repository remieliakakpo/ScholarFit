"""Types d'opportunités affichés : choisis dans l'administration, masqués partout ailleurs."""
import pytest

from app.vocab import KINDS


@pytest.fixture()
def restore_kinds(client, admin):
    yield
    client.put("/api/admin/types", headers=admin, json={"kinds_enabled": list(KINDS)})


def test_all_kinds_shown_by_default(client, admin, restore_kinds):
    client.put("/api/admin/types", headers=admin, json={"kinds_enabled": list(KINDS)})
    rows = client.get("/api/admin/types", headers=admin).json()
    assert [r["kind"] for r in rows] == list(KINDS) and all(r["enabled"] for r in rows)
    assert set(client.get("/api/meta").json()["kinds"]) == set(KINDS)


def test_hidden_kind_disappears_everywhere(client, admin, demo, restore_kinds):
    body = {"kind": "concours", "title": "Concours masqué test", "organization": "Org", "official_url": "https://example.org/concours-masque",
            "levels": ["BAC5"]}
    sid = client.post("/api/admin/scholarships", headers=admin, json=body).json()["id"]
    assert client.get(f"/api/scholarships/{sid}").status_code == 200

    r = client.put("/api/admin/types", headers=admin, json={"kinds_enabled": ["bourse", "stage"]})
    assert r.status_code == 200 and r.json()["kinds_enabled"] == ["bourse", "stage"]
    assert set(client.get("/api/meta").json()["kinds"]) == {"bourse", "stage"}
    assert client.get(f"/api/scholarships/{sid}").status_code == 404  # fiche d'un type masqué
    assert client.get("/api/scholarships", params={"kind": "concours"}).json()["total"] == 0
    everything = client.get("/api/scholarships", params={"per_page": 100, "include_expired": True}).json()["items"]
    assert all(i["kind"] in ("bourse", "stage") for i in everything)
    assert set(client.get("/api/stats").json()["by_kind"]) == {"bourse", "stage"}
    assert client.get("/api/stats/countries", params={"kind": "conference"}).json() == []
    tout = client.get("/api/matches", headers=demo, params={"kind": "tout"}).json()["items"]
    assert all(m["scholarship"]["kind"] in ("bourse", "stage") for m in tout)
    rows = {r["kind"]: r for r in client.get("/api/admin/types", headers=admin).json()}
    assert rows["concours"]["enabled"] is False and rows["concours"]["total"] >= 1  # toujours en base

    log = client.get("/api/admin/audit", headers=admin, params={"action": "types"}).json()["items"]
    assert log and log[0]["details"]["apres"] == ["bourse", "stage"]


def test_types_rules(client, admin, demo, restore_kinds):
    assert client.put("/api/admin/types", headers=demo, json={"kinds_enabled": ["bourse"]}).status_code == 403
    assert client.put("/api/admin/types", headers=admin, json={"kinds_enabled": []}).status_code == 422
    assert client.put("/api/admin/types", headers=admin, json={"kinds_enabled": ["emploi"]}).status_code == 422


def test_hidden_kind_not_collected(client, admin, monkeypatch, restore_kinds):
    """Une catégorie d'un type masqué n'est pas lue : aucun coût d'IA pour elle."""
    from app.db import SessionLocal
    from app.models import Source
    from app.scrapers import collector

    client.put("/api/admin/types", headers=admin, json={"kinds_enabled": ["bourse", "stage"]})
    read = []

    class FakeFetcher:
        def __init__(self, *a, **k):
            pass

        def get(self, url):
            read.append(url)
            raise RuntimeError("pas de flux")

        def close(self):
            pass

    monkeypatch.setattr(collector, "PoliteFetcher", FakeFetcher)
    monkeypatch.setattr(collector, "_crawl_detail_pages", lambda *a, **k: (0, 0))
    cfg = {"feeds": [{"url": "https://oc.example.org/category/internships/feed/", "kind": "stage"},
                     {"url": "https://oc.example.org/category/competitions/feed/", "kind": "concours"}], "paths": []}
    db = SessionLocal()
    try:
        collector.run_site(db, Source(name="OC visibilité", url="https://oc.example.org", connector="site"), cfg)
    finally:
        db.close()
    assert read == ["https://oc.example.org/category/internships/feed/"]
