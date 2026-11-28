"""Connecteur Campus Bourses : fiche de l'API mise en HTML, valeurs imposées par la source."""
from app.scrapers.campusbourses import program_html, program_url
from app.scrapers.extract import html_to_text, official_link

PROGRAM = {
    "bourseId": 321, "title": 'Bourses "CONCORDE"', "synthese": "Bourses pour étudier en France.",
    "description": "<div>Pour des études de master ou de doctorat.</div>", "montant": "", "duree": "12 mois",
    "inscriptionUrl": "", "web1": "ANBG", "url1": "https://www.anbg-ga.com/", "url2": "javascript:alert(1)",
}


def test_program_html_keeps_sections_and_official_link():
    html = program_html(PROGRAM)
    title, text = html_to_text(html)
    assert "CONCORDE" in title
    assert "Durée" in text and "12 mois" in text and "Montant" not in text  # sections vides omises
    assert "javascript:" not in html  # seuls les liens http(s) sont gardés
    assert official_link(html, program_url(321)) == "https://www.anbg-ga.com/"
    assert program_url(321) == "https://campusbourses.campusfrance.org/#/program/321"


def test_finish_record_applies_defaults_and_overrides(monkeypatch):
    from app.scrapers import collector

    saved = {}
    monkeypatch.setattr(collector, "upsert", lambda db, rec, src: (saved.update(rec), (None, True))[1])
    ctx = {"url": program_url(321), "aggregator": True, "category_kind": "bourse", "official_link": "https://www.anbg-ga.com/",
           "defaults": {"study_countries": ["FR"]}, "overrides": {"recurring": True}}
    rec = {"title": "Bourses Concorde", "kind": "formation", "official_url": program_url(321), "study_countries": []}
    assert collector.finish_record(None, None, rec, ctx) is True
    assert saved["kind"] == "bourse" and saved["recurring"] is True and saved["study_countries"] == ["FR"]
    assert saved["official_url"] == "https://www.anbg-ga.com/" and saved["source_page"] == program_url(321)
    # un pays déjà trouvé par l'extraction n'est pas remplacé
    rec = {"title": "Mitacs", "official_url": program_url(5), "study_countries": ["CA"]}
    collector.finish_record(None, None, rec, {**ctx, "url": program_url(5)})
    assert saved["study_countries"] == ["CA"]
