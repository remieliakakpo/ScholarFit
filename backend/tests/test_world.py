"""Collecte mondiale, dates limites, fiches détaillées, questionnaire, offres, liens."""
from datetime import date, timedelta

import httpx

from app.deadlines import deadline_info
from app.models import Scholarship
from tests.conftest import login


def _s(**kw) -> Scholarship:
    base = dict(title="Test", organization="Org", official_url="https://ex.org", recurring=True, status="active",
                deadline_estimated=False, previous_deadline=None)
    base.update(kw)
    return Scholarship(**base)


def test_deadline_states():
    today = date(2026, 11, 19)
    assert deadline_info(_s(deadline=today + timedelta(days=5)), today).status == "urgente"
    assert deadline_info(_s(deadline=today + timedelta(days=30)), today).status == "bientot"
    assert deadline_info(_s(deadline=today + timedelta(days=200)), today).status == "ouverte"
    assert deadline_info(_s(deadline=None), today).status == "inconnue"
    past = deadline_info(_s(deadline=today - timedelta(days=3)), today)
    assert past.status == "expiree" and past.priority == 5 and past.next_expected is not None
    closed = deadline_info(_s(deadline=date(2027, 11, 4), previous_deadline=date(2026, 11, 4), deadline_estimated=True), today)
    assert closed.status == "expiree" and "Prochaine session" in closed.label


def test_scholarship_detail_fields(client):
    s = client.get("/api/scholarships", params={"q": "chevening", "include_expired": True}).json()["items"][0]
    for k in ("eligibility_notes", "documents", "application_steps", "apply_url", "link_status", "deadline_status",
              "priority", "deadline_label", "regions"):
        assert k in s, k
    assert s["regions"] == ["europe"]
    assert any("expérience professionnelle" in n for n in s["eligibility_notes"])
    assert {d["code"] for d in s["documents"]} >= {"lettre", "recommandation"}
    assert len(s["application_steps"]) >= 4
    assert s["apply_url"].startswith("https://")


def test_expired_hidden_by_default_and_flagged(client):
    default = client.get("/api/scholarships", params={"per_page": 100}).json()
    allx = client.get("/api/scholarships", params={"per_page": 100, "include_expired": True}).json()
    assert allx["total"] >= default["total"]
    assert all(i["deadline_status"] != "expiree" for i in default["items"])
    only = client.get("/api/scholarships", params={"deadline_status": "expiree", "per_page": 100}).json()
    assert all(i["deadline_status"] == "expiree" for i in only["items"])
    pr = client.get("/api/scholarships", params={"sort": "priority", "per_page": 100}).json()["items"]
    assert [i["priority"] for i in pr] == sorted(i["priority"] for i in pr)


def test_region_filter_and_world_stats(client):
    for region in ("afrique", "europe", "amerique", "asie", "oceanie"):
        r = client.get("/api/scholarships", params={"region": region, "include_expired": True, "per_page": 100}).json()
        assert r["total"] > 0, region
        assert all(region in i["regions"] for i in r["items"])
    rows = client.get("/api/stats/countries", params={"include_expired": True}).json()
    assert len(rows) >= 40  # pays d'études couverts sur tous les continents
    assert {r["region"] for r in rows} == {"afrique", "europe", "amerique", "asie", "oceanie"}
    assert rows[0]["count"] >= rows[-1]["count"] and rows[0]["lat"] is not None
    fr = next(r for r in rows if r["code"] == "FR")
    assert fr["count"] > 1  # le nombre réel, pas « 1 »
    st = client.get("/api/stats").json()
    assert st["total"] >= 80 and st["open"] + st["expired"] == st["total"]
    assert all(v >= 0 for v in st["by_region"].values())


def test_questionnaire_anonymous_and_logged(client):
    steps = client.get("/api/questionnaire").json()["steps"]
    assert len(steps) == 5
    answers = {
        "nationalities": ["SN"], "birth_date": "2002-04-12", "current_level": "BAC3", "target_level": "BAC5",
        "domain": "informatique", "grade_average": "15,5", "wished_regions": ["europe", "asie"],
        "languages": ["fr", "en"], "language_scores": {"IELTS": "6.5"}, "help_preference": "ne_sait_pas",
        "applications_planned": 4,
    }
    anon = client.post("/api/questionnaire", json={"answers": answers}).json()
    assert anon["total_matches"] > 3 and len(anon["items"]) == 3
    assert all(i["score"] is None for i in anon["items"]) and anon["profile_saved"] is False
    assert anon["recommended_offer"] == "premium"  # 4 bourses visées
    r = client.post("/api/auth/register", json={"email": "quiz@example.org", "password": "motdepasse1"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    res = client.post("/api/questionnaire", headers=h, json={"answers": answers}).json()
    assert res["profile_saved"] and res["total_matches"] == anon["total_matches"]
    assert all(isinstance(i["score"], int) for i in res["items"])
    for i in res["items"]:
        assert set(i["scholarship"]["study_countries"]) & {"FR", "DE", "GB", "JP", "CN", "KR"} or i["scholarship"]["study_countries"] == [] \
            or {"europe", "asie"} & set(i["scholarship"]["regions"])
    # Bourses des continents choisis d'abord, puis « Autres bourses disponibles »
    assert res["has_destination"] and res["destination_total"] == sum(1 for i in res["items"] if i["in_destination"])
    flags = [i["in_destination"] for i in res["items"]]
    assert flags == sorted(flags, reverse=True)
    dest_q = next(q for st in steps for q in st["questions"] if q["id"] == "wished_countries")
    assert dest_q["filter_by"] == "wished_regions" and {"value": "FR", "region": "europe"}.items() <= next(o for o in dest_q["options"] if o["value"] == "FR").items()
    p = client.get("/api/profile", headers=h).json()
    assert p["wished_regions"] == ["europe", "asie"] and p["grade_average"] == 15.5
    assert client.post("/api/questionnaire", json={"answers": {"grade_average": 25}}).status_code == 422


def test_offers_and_paid_coaching(client):
    offers = client.get("/api/offres").json()
    by = {o["code"]: o for o in offers}
    assert by["standard"]["price"] == 15000 and by["standard"]["price_label"] == "15 000 F CFA"
    assert by["premium"]["price"] == 35000 and by["autonome"]["price"] == 0
    assert sum(o["recommended"] for o in offers) == 1
    h = login(client, "quiz@example.org", "motdepasse1")
    body = {"goal": "Je veux un dossier solide pour un master en Europe.", "needs": ["cv"], "share_consent": True}
    assert client.post("/api/accompagnement", headers=h, json={**body, "offer": "autonome"}).status_code == 422
    r = client.post("/api/accompagnement", headers=h, json={**body, "offer": "premium"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["offer"] == "premium" and c["price"] == 35000 and c["payment_status"] == "a_payer"
    admin = login(client, "admin@example.org", "admin12345")
    r = client.patch(f"/api/admin/accompagnement/{c['id']}/paiement", headers=admin, json={"payment_status": "paye"})
    assert r.status_code == 200 and r.json()["payment_status"] == "paye"


def test_link_check_statuses():
    from app.linkcheck import check_url

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/mort":
            return httpx.Response(404)
        if req.url.path == "/ancien":
            return httpx.Response(301, headers={"Location": "https://ex.org/nouveau"})
        if req.url.path == "/robot" and req.method == "HEAD":
            return httpx.Response(403)
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as c:
        assert check_url("https://ex.org/ok", c)[0] == "ok"
        assert check_url("https://ex.org/mort", c)[0] == "casse"
        st, final, _ = check_url("https://ex.org/ancien", c)
        assert st == "redirige" and final.endswith("/nouveau")
        assert check_url("https://ex.org/robot", c)[0] == "ok"  # HEAD refusé, GET accepté


def test_ai_discovery_keeps_only_live_links(client, monkeypatch):
    from app.db import SessionLocal
    from app.scrapers import discovery
    from app.scrapers.collector import sync_sources

    monkeypatch.setattr(discovery, "get_settings", lambda: type("S", (), {"ai_enabled": True, "ai_discovery_enabled": True, "ai_discovery_max_searches": 1})())
    monkeypatch.setattr(discovery, "ask_web", lambda *a, **k: "notes")
    rec = dict(title="Bourse de test Océanie", organization="Fondation X", official_url="https://vivant.example/b", summary="Test.",
               levels=["BAC5"], study_countries=["FJ"], eligible_nationalities=["ALL"], domains=["tous"], languages=["en"],
               amount=None, currency=None, amount_period=None, coverage=["frais"], full_funding=False, deadline="2099-03-01",
               max_age=None, requirements=["cv"], eligibility=["Condition."], application_steps=["Étape 1."], apply_via="direct")
    dead = {**rec, "title": "Bourse au lien mort", "official_url": "https://mort.example/b"}
    monkeypatch.setattr(discovery, "ask_json", lambda *a, **k: {"scholarships": [rec, dead]})
    monkeypatch.setattr(discovery, "check_url", lambda url, http: ("casse", None, 404) if "mort" in url else ("ok", url, 200))
    db = SessionLocal()
    try:
        src = [s for s in sync_sources(db) if s.connector == "ai_discovery"][0]
        created, _ = discovery.run_ai_discovery(db, src, {"zones_per_run": 1})
        assert created == 1
    finally:
        db.close()
    r = client.get("/api/scholarships", params={"q": "Océanie"}).json()
    assert r["total"] == 1 and r["items"][0]["status"] == "a_verifier" and r["items"][0]["link_status"] == "ok"
    assert client.get("/api/scholarships", params={"q": "lien mort"}).json()["total"] == 0


def test_old_database_gets_new_columns(tmp_path):
    """Une base créée avec l'ancienne version reçoit les nouvelles colonnes au démarrage."""
    import sqlalchemy as sa

    from app import db as dbmod

    path = tmp_path / "ancienne.db"
    eng = sa.create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY, slug VARCHAR(200), title VARCHAR(300))"))
    old = dbmod.engine
    dbmod.engine = eng
    try:
        dbmod._add_missing_columns()
    finally:
        dbmod.engine = old
    cols = {c["name"] for c in sa.inspect(eng).get_columns("scholarships")}
    assert {"eligibility", "link_status", "deadline_estimated", "apply_via"} <= cols


def test_register_rules(client):
    weak = client.post("/api/auth/register", json={"email": "faible@example.org", "password": "abcdefgh"})
    assert weak.status_code == 422 and "chiffre" in weak.json()["detail"]
    assert client.get("/api/auth/email-disponible", params={"email": "Demo@Example.org "}).json()["available"] is False
    r = client.post("/api/auth/register", json={"email": " Majuscules@Example.org", "password": "motdepasse1"})
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"email": "majuscules@example.org", "password": "motdepasse1"}).status_code == 200
    dup = client.post("/api/auth/register", json={"email": "majuscules@example.org", "password": "motdepasse1"})
    assert dup.status_code == 409


def test_kinds_filters_and_stats(client):
    for kind in ("bourse", "stage", "conference"):
        r = client.get("/api/scholarships", params={"kind": kind, "include_expired": True, "per_page": 100}).json()
        assert r["total"] > 0 and all(i["kind"] == kind for i in r["items"]), kind
    stage = client.get("/api/scholarships", params={"kind": "stage", "q": "Blue Book", "include_expired": True}).json()["items"][0]
    assert stage["kind_label"] == "Stage" and stage["duration"] == "5 mois"
    assert any("Durée" in n for n in stage["eligibility_notes"]) and "stage" in stage["application_steps"][0]
    conf = client.get("/api/scholarships", params={"kind": "conference", "q": "Indaba", "include_expired": True}).json()["items"][0]
    assert conf["event_start"] and conf["event_end"] >= conf["event_start"]
    assert any(n.startswith("Dates") for n in conf["eligibility_notes"])
    st = client.get("/api/stats").json()
    assert st["by_kind"]["stage"] >= 1 and st["by_kind"]["conference"] >= 1
    assert "kinds" in client.get("/api/meta").json()
    assert client.get("/api/stats/countries", params={"kind": "stage", "include_expired": True}).json()


def test_guess_kind_and_official_link():
    from app.scrapers.collector import guess_kind
    from app.scrapers.extract import official_link

    assert guess_kind("Stage rémunéré à la BAD") == "stage"
    assert guess_kind("Internship Programme 2027") == "stage"
    assert guess_kind("Sommet africain de la jeunesse") == "conference"
    assert guess_kind("Bourse Chevening") == "bourse"
    html = """<html><body><nav><a href="https://facebook.com/x">fb</a></nav><article>
      <p>Voici la bourse.</p><a href="https://afri-carrieres.com/autre">autre annonce</a>
      <a href="https://twitter.com/share">partager</a>
      <p>Pour postuler, rendez-vous sur le site officiel :</p><a href="https://www.chevening.org/apply">Cliquez ici</a>
    </article></body></html>"""
    assert official_link(html, "https://afri-carrieres.com/bourse-chevening") == "https://www.chevening.org/apply"
    assert official_link("<article><a href='/x'>interne</a></article>", "https://afri-carrieres.com/a") is None


def test_aggregator_site_connector(client, monkeypatch):
    from app.db import SessionLocal
    from app.scrapers import collector

    home = """<html><body>
      <a href="https://afri-carrieres.com/bourse-master-suede-2027-entierement-financee">Bourse</a>
      <a href="https://afri-carrieres.com/stage-remunere-banque-mondiale-2027">Stage</a>
      <a href="https://afri-carrieres.com/la-sonatel-recrute-un-comptable-cdi">Emploi</a>
      <a href="https://autre-site.com/bourse-de-test-ailleurs">externe</a></body></html>"""
    pages = {
        "https://afri-carrieres.com/bourse-master-suede-2027-entierement-financee":
            "<h1>Bourse de master en Suède pour Africains 2027</h1><article><p>" + "Bourse entièrement financée pour un master en Suède. " * 3
            + "Date limite : 15 mars 2099.</p><p>Pour postuler :</p><a href='https://si.se/apply'>Site officiel</a></article>",
        "https://afri-carrieres.com/stage-remunere-banque-mondiale-2027":
            "<h1>Stage rémunéré à la Banque mondiale 2027</h1><article><p>" + "Stage de trois mois pour étudiants de master à Washington. " * 3
            + "</p><a href='https://www.worldbank.org/internship'>Postuler ici</a></article>",
    }

    class FakeFetcher:
        def __init__(self, *a, **k): ...
        def get(self, url, use_cache=True):
            if url.endswith("/feed/"):
                raise ValueError("pas de flux")
            if url.rstrip("/") == "https://afri-carrieres.com":
                return home
            if url in pages:
                return pages[url]
            raise AssertionError(f"page inattendue : {url}")
        def allowed(self, url): return True
        def close(self): ...

    monkeypatch.setattr(collector, "PoliteFetcher", FakeFetcher)
    db = SessionLocal()
    try:
        assert collector.run_source(db, "Afri-Carrières").startswith("ok : 2 nouvelle")
    finally:
        db.close()
    b = client.get("/api/scholarships", params={"q": "master en Suède pour Africains"}).json()["items"][0]
    assert b["kind"] == "bourse" and b["official_url"] == "https://si.se/apply" and b["source_page"].startswith("https://afri-carrieres.com/")
    s = client.get("/api/scholarships", params={"kind": "stage", "q": "Banque mondiale 2027"}).json()["items"][0]
    assert s["official_url"] == "https://www.worldbank.org/internship"
    assert client.get("/api/scholarships", params={"q": "comptable"}).json()["total"] == 0


def test_country_exact_matches_stats(client):
    for kind in ("bourse", "stage"):
        for row in client.get("/api/stats/countries", params={"kind": kind}).json()[:10]:
            r = client.get("/api/scholarships", params={"country": row["code"], "country_exact": True, "kind": kind}).json()
            assert r["total"] == row["count"], (kind, row)
            assert all(row["code"] in i["study_countries"] for i in r["items"])
    loose = client.get("/api/scholarships", params={"country": "GH", "kind": "bourse"}).json()["total"]
    exact = client.get("/api/scholarships", params={"country": "GH", "kind": "bourse", "country_exact": True}).json()["total"]
    assert loose >= exact
