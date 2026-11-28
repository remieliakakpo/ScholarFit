"""Tous les types d'opportunités et la source Opportunities Corners (flux par catégorie)."""
import pytest

from app.vocab import KINDS

RSS = """<?xml version="1.0"?><rss><channel><link>https://oc.example.org/</link>{items}</channel></rss>"""
ITEM = "<item><title>{t}</title><link>{u}</link></item>"


def test_all_kinds_known():
    assert set(KINDS) == {"bourse", "stage", "conference", "formation", "concours", "echange", "fellowship", "cours_en_ligne"}


@pytest.mark.parametrize("kind", ["formation", "concours", "echange", "fellowship", "cours_en_ligne", "tout"])
def test_api_accepts_new_kinds(client, kind):
    if kind != "tout":
        assert client.get("/api/scholarships", params={"kind": kind}).status_code == 200
        assert client.get("/api/stats/countries", params={"kind": kind}).status_code == 200
    assert client.post("/api/questionnaire", params={"kind": kind}, json={"answers": {}}).status_code in (200, 422)
    assert client.get("/api/scholarships", params={"kind": "emploi"}).status_code == 422


def test_admin_can_create_each_kind(client, admin):
    for kind in KINDS:
        body = {"kind": kind, "title": f"Offre test {kind}", "organization": "Org", "official_url": f"https://example.org/type-{kind}",
                "levels": ["BAC5"]}
        r = client.post("/api/admin/scholarships", headers=admin, json=body)
        assert r.status_code == 201 and r.json()["kind"] == kind and r.json()["kind_label"]
    stats = client.get("/api/stats").json()
    assert set(KINDS) <= set(stats["by_kind"])


def test_kind_guessing():
    from app.scrapers.collector import guess_kind

    cases = {"Google Online Course 2027": "cours_en_ligne", "Africa Innovation Challenge prize": "concours",
             "Erasmus summer school": "echange", "Mandela Washington Fellowship": "fellowship",
             "AI bootcamp training": "formation", "UN internship": "stage", "Youth summit Morocco": "conference",
             "Chevening scholarship": "bourse"}
    for text, kind in cases.items():
        assert guess_kind(text) == kind, text


def test_category_feeds_give_kind_and_skip_guides_and_jobs(client, monkeypatch):
    """Opportunities Corners : un flux par catégorie donne le type ; guides de visa et emplois ne sont pas lus."""
    from app.models import Source
    from app.scrapers import collector

    feeds = {
        "https://oc.example.org/category/competitions/feed/": RSS.format(items=ITEM.format(t="Hackathon", u="https://oc.example.org/global-hackathon-2027/")),
        "https://oc.example.org/category/online-courses/feed/": RSS.format(items=(
            ITEM.format(t="Cours", u="https://oc.example.org/free-ai-course-2027/")
            + ITEM.format(t="Visa", u="https://oc.example.org/canada-student-visa-guide/")
            + ITEM.format(t="Emploi", u="https://oc.example.org/emirates-cabin-crew-jobs-2026/"))),
    }

    class FakeFetcher:
        def __init__(self, *a, **k):
            pass

        def get(self, url):
            if url in feeds:
                return feeds[url]
            raise RuntimeError("page 2 absente")

        def close(self):
            pass

    seen = {}
    monkeypatch.setattr(collector, "PoliteFetcher", FakeFetcher)
    monkeypatch.setattr(collector, "_crawl_detail_pages",
                        lambda db, source, links, fetcher, limit, aggregator=False, kind=None, kinds=None: seen.update(links=links, kinds=kinds) or (0, 0))
    cfg = {"feed_pages": 2, "exclude_pattern": r"(visa|guide|jobs?\b)", "feeds": [
        {"url": "https://oc.example.org/category/competitions/feed/", "kind": "concours"},
        {"url": "https://oc.example.org/category/online-courses/feed/", "kind": "cours_en_ligne"},
    ]}
    src = Source(name="OC test", url="https://oc.example.org", connector="site")
    collector.run_site(None, src, cfg)
    assert seen["links"] == ["https://oc.example.org/global-hackathon-2027/", "https://oc.example.org/free-ai-course-2027/"]
    assert seen["kinds"]["https://oc.example.org/global-hackathon-2027/"] == "concours"
    assert seen["kinds"]["https://oc.example.org/free-ai-course-2027/"] == "cours_en_ligne"


def test_sources_file_enables_existing_sources(client):
    """Activer une source dans sources.json s'applique aussi à une base existante."""
    from app.db import SessionLocal
    from app.models import Source
    from app.scrapers.collector import load_source_configs, sync_sources

    db = SessionLocal()
    try:
        sync_sources(db)
        db.commit()
        cf = db.query(Source).filter(Source.name.like("Campus France%")).one()
        cf.enabled = False  # comme dans une base créée avant l'activation
        db.commit()
        sync_sources(db)
        db.commit()
        assert db.query(Source).filter(Source.name.like("Campus France%")).one().enabled is True
        corners = next(c for c in load_source_configs() if c["name"] == "Opportunities Corners")
        assert {f["kind"] for f in corners["feeds"]} == set(KINDS)
        # toutes activées, sauf EURAXESS : plus de flux, et le site bloque les robots (voir sa note)
        off = [c["name"] for c in load_source_configs() if not c.get("enabled", True)]
        assert len(off) == 1 and off[0].startswith("EURAXESS")
    finally:
        db.close()


def test_feed_links_are_items_only():
    """Le lien du flux lui-même (accueil ou catégorie) n'est pas une annonce ; RSS et Atom sont lus."""
    import xml.etree.ElementTree as ET

    from app.scrapers.collector import feed_item_links

    rss = ET.fromstring("<rss><channel><link>https://s.example.org/category/x/</link>"
                        "<item><link>https://s.example.org/annonce-1/</link></item></channel></rss>")
    atom = ET.fromstring('<feed xmlns="http://www.w3.org/2005/Atom"><link href="https://s.example.org/"/>'
                         '<entry><link href="https://s.example.org/annonce-2/"/></entry></feed>')
    assert feed_item_links(rss) == ["https://s.example.org/annonce-1/"]
    assert feed_item_links(atom) == ["https://s.example.org/annonce-2/"]


def test_category_kind_wins_over_guess(client):
    """Le type de la catégorie du site prime sur le type deviné par les règles ou l'IA."""
    from app.db import SessionLocal
    from app.scrapers.collector import finish_record

    db = SessionLocal()
    try:
        rec = {"title": "UNIQLO Global Management Program test", "organization": "Org", "official_url": "https://example.org/uniqlo-test",
               "kind": "bourse"}
        finish_record(db, None, rec, {"url": "https://oc.example.org/uniqlo/", "kind": "formation", "category_kind": "formation"})
        db.commit()
        from app.models import Scholarship

        assert db.query(Scholarship).filter_by(title="UNIQLO Global Management Program test").one().kind == "formation"
    finally:
        db.close()
