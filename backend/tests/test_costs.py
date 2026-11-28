"""Économies d'IA : pages déjà lues, travaux par lots (Batch API), réponses réutilisées, fréquence."""
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

PAGE = "<html><head><title>Bourse Test {n}</title></head><body><h1>Bourse Test {n}</h1><p>{body}</p></body></html>"


def _db():
    from app.db import SessionLocal

    return SessionLocal()


class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url):
        self.calls.append(url)
        return self.pages[url]


@pytest.fixture()
def source(client):
    from app.models import Source

    db = _db()
    try:
        src = db.query(Source).filter_by(name="Test économies").first() or Source(name="Test économies", url="https://agg.example.org", connector="site")
        db.add(src)
        db.commit()
        return src.id
    finally:
        db.close()


@pytest.fixture()
def ai_on(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "cle-de-test")
    monkeypatch.setattr(s, "ai_use_batch", True)
    return s


def test_rejected_announcement_is_not_read_again(client, source, monkeypatch):
    """La fuite corrigée : une annonce écartée (offre d'emploi…) n'est plus relue ni repayée à chaque passage."""
    from app.models import Source
    from app.scrapers import collector

    calls = []
    monkeypatch.setattr(collector, "extract", lambda html, url, use_ai=True: calls.append(url) or None)
    url = "https://agg.example.org/offre-emploi-1"
    f = FakeFetcher({url: PAGE.format(n=1, body="Recrutement CDI comptable")})
    db = _db()
    try:
        src = db.get(Source, source)
        collector._crawl_detail_pages(db, src, [url], f, limit=10, aggregator=True)
        db.commit()
        collector._crawl_detail_pages(db, src, [url], f, limit=10, aggregator=True)
        db.commit()
    finally:
        db.close()
    assert calls == [url] and f.calls == [url]  # analysée une fois, plus jamais téléchargée


def test_unchanged_page_is_not_extracted_again(client, source, monkeypatch):
    from app.models import Source
    from app.scrapers import collector

    calls = []

    def fake_extract(html, url, use_ai=True):
        calls.append(url)
        return {"title": "Bourse Test inchangée", "official_url": "https://officiel.example.org/b1", "organization": "Org"}

    monkeypatch.setattr(collector, "extract", fake_extract)
    url = "https://liste.example.org/bourse-1"
    pages = {url: PAGE.format(n=2, body="Texte d'origine")}
    f = FakeFetcher(pages)
    db = _db()
    try:
        src = db.get(Source, source)
        for _ in range(2):
            collector._crawl_detail_pages(db, src, [url], f, limit=10)
            db.commit()
        assert len(calls) == 1  # même texte : pas de nouvel appel
        pages[url] = PAGE.format(n=2, body="Texte modifié : nouvelle date limite")
        collector._crawl_detail_pages(db, src, [url], f, limit=10)
        db.commit()
        assert len(calls) == 2  # la page a changé : on la relit
    finally:
        db.close()


def _succeeded(job_id, data, stop="end_turn"):
    msg = SimpleNamespace(stop_reason=stop, model="claude-opus-5-5",
                          content=[SimpleNamespace(type="text", text=json.dumps(data))],
                          usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0, cache_read_input_tokens=0,
                                                cache_creation_input_tokens=0, server_tool_use=None))
    return SimpleNamespace(custom_id=f"job-{job_id}", result=SimpleNamespace(type="succeeded", message=msg))


class FakeBatches:
    def __init__(self):
        self.created, self.results_for = [], {}

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"lot_{len(self.created)}", processing_status="in_progress")

    def retrieve(self, bid):
        return SimpleNamespace(id=bid, processing_status="ended")

    def results(self, bid):
        return iter(self.results_for.get(bid, []))


def test_extraction_goes_through_batch_with_rules_fallback(client, source, ai_on, monkeypatch):
    from app.ai import batch
    from app.models import AICost, AIJob, Scholarship, SeenPage, Source
    from app.scrapers import collector

    monkeypatch.setattr(collector, "extract", lambda *a, **k: pytest.fail("pas d'appel immédiat quand les lots sont actifs"))
    fake = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches()))
    monkeypatch.setattr(batch, "_client", lambda: fake)
    u1, u2 = "https://agg.example.org/bourse-lot-1", "https://agg.example.org/bourse-lot-2"
    f = FakeFetcher({u1: PAGE.format(n=3, body="Bourse de master au Canada, date limite 2027"),
                     u2: PAGE.format(n=4, body="Bourse de doctorat en France, date limite 2027")})
    db = _db()
    try:
        collector._crawl_detail_pages(db, db.get(Source, source), [u1, u2], f, limit=10, aggregator=True)
        db.commit()
        jobs = db.query(AIJob).filter(AIJob.kind == "extract", AIJob.status == "en_attente").all()
        assert len(jobs) == 2
        assert db.query(SeenPage).filter_by(url=u1).one().outcome == "en_attente"

        assert batch.submit_pending(db) == 2
        req = fake.messages.batches.created[0][0]["params"]
        assert "fallbacks" not in req and req["output_config"]["format"]["type"] == "json_schema"
        bid = jobs[0].batch_id
        deadline = str(date.today() + timedelta(days=120))
        record = {"is_scholarship": True, "kind": "bourse", "official_link": "https://officiel.example.org/lot-1", "event_start": None,
                  "event_end": None, "city": None, "remote": False, "duration": None, "eligibility": [], "application_steps": [],
                  "title": "Bourse lot Canada", "organization": "Fondation Lot", "summary": "Master au Canada.", "levels": ["BAC5"],
                  "study_countries": ["CA"], "eligible_nationalities": ["ALL"], "domains": ["tous"], "languages": ["fr"], "amount": None,
                  "currency": None, "amount_period": None, "coverage": [], "full_funding": True, "deadline": deadline, "max_age": None,
                  "requirements": ["cv"], "target_groups": [],
                  "evidence": {"deadline": "date limite 2027", "eligibility": None, "funding": None}}  # preuve présente dans la page
        errored = SimpleNamespace(custom_id=f"job-{jobs[1].id}", result=SimpleNamespace(type="errored"))
        fake.messages.batches.results_for[bid] = [_succeeded(jobs[0].id, record), errored]
        out = batch.collect_results(db)
        assert out == {"faits": 1, "echecs": 1}
        s = db.query(Scholarship).filter_by(title="Bourse lot Canada").one()
        assert s.official_url == "https://officiel.example.org/lot-1" and s.source_page == u1
        assert db.query(SeenPage).filter_by(url=u1).one().outcome == "fiche"
        failed = db.get(AIJob, jobs[1].id)
        assert failed.status == "echec" and db.query(SeenPage).filter_by(url=u2).one().outcome in ("fiche", "ecartee")  # repli par règles
        cost = db.query(AICost).filter_by(purpose="lot_extract").order_by(AICost.id.desc()).first()
        assert cost.cost_usd == pytest.approx(ai_on.ai_price_input_per_mtok * 0.5)  # moitié prix
    finally:
        db.close()


def test_translations_queued_once(client, ai_on, monkeypatch):
    from app.ai import batch
    from app.models import AIJob
    from app.translate import translate_missing

    monkeypatch.setattr("app.translate.ask_json", lambda *a, **k: pytest.fail("pas d'appel immédiat"))
    db = _db()
    try:
        db.query(AIJob).filter(AIJob.kind == "translate").delete()
        db.commit()
        from app.models import Scholarship

        s = db.query(Scholarship).filter(Scholarship.status != "expiree").first()
        saved = s.translations
        s.translations = {}  # plus de version anglaise : à traduire
        db.commit()
        try:
            first = translate_missing(db, limit=5)
            second = translate_missing(db, limit=5)
            assert first >= 1 and second == 0  # déjà en file : pas de doublon
            assert s.id in batch.pending_targets(db, "translate", "scholarship_id")
        finally:  # base partagée par les autres tests : on remet la fiche et la file en l'état
            s.translations = saved
            db.query(AIJob).filter(AIJob.kind == "translate").delete()
            db.commit()
    finally:
        db.close()


def test_identical_request_reuses_answer(client, monkeypatch):
    from app.ai import client as ai_client

    calls = []

    class Msgs:
        def create(self, **kw):
            calls.append(1)
            return SimpleNamespace(stop_reason="end_turn", model=kw["model"], usage=None,
                                   content=[SimpleNamespace(type="text", text='{"ok": true}')])

    monkeypatch.setattr(ai_client, "_get_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=Msgs())))
    monkeypatch.setattr(ai_client.costs, "over_budget", lambda: False)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    assert ai_client.ask_json("sys", "même CV, même bourse", schema, cache=True) == {"ok": True}
    assert ai_client.ask_json("sys", "même CV, même bourse", schema, cache=True) == {"ok": True}
    assert len(calls) == 1  # la seconde demande identique n'a rien coûté
    ai_client.ask_json("sys", "même CV, même bourse", schema)  # sans cache=True : nouvel appel (ex. régénérer une lettre)
    assert len(calls) == 2


def test_sources_collected_once_a_week():
    from app.scrapers.collector import load_source_configs

    freqs = {c["frequency_hours"] for c in load_source_configs() if c.get("frequency_hours")}
    assert freqs == {168}  # sites et découverte : une fois par semaine


def test_doubtful_record_gets_targeted_review(client, source, ai_on, monkeypatch):
    """Extraction en deux temps : premier passage économique, contrôle sans IA, relecture ciblée seulement si douteux."""
    from app.ai import batch
    from app.models import AICost, AIJob, Scholarship, SeenPage, Source
    from app.scrapers import collector

    monkeypatch.setattr(ai_on, "extract_model", "claude-haiku-5-5")
    fake = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches()))
    monkeypatch.setattr(batch, "_client", lambda: fake)
    url = "https://agg.example.org/bourse-a-relire"
    body = "Bourse de master en Allemagne pour étudiants africains. Date limite : 30 avril 2027."
    db = _db()
    try:
        collector._crawl_detail_pages(db, db.get(Source, source), [url], FakeFetcher({url: PAGE.format(n=9, body=body)}),
                                      limit=5, aggregator=True)
        db.commit()
        batch.submit_pending(db)
        job = next(j for j in db.query(AIJob).filter(AIJob.kind == "extract").all() if (j.context or {}).get("url") == url)
        sent = {r["custom_id"]: r for r in fake.messages.batches.created[-1]}
        assert sent[f"job-{job.id}"]["params"]["model"] == "claude-haiku-5-5"  # premier passage sur le modèle économique
        draft = {"is_scholarship": True, "kind": "bourse", "official_link": None, "event_start": None, "event_end": None,
                 "city": None, "remote": False, "duration": None, "eligibility": [], "application_steps": [],
                 "title": "Bourse à relire Allemagne", "organization": "Org relue", "summary": "Master en Allemagne.",
                 "levels": [], "study_countries": ["DE"], "eligible_nationalities": ["AFRICA"], "domains": ["tous"], "languages": [],
                 "amount": None, "currency": None, "amount_period": None, "coverage": [], "full_funding": False,
                 "deadline": None, "max_age": None, "requirements": [], "target_groups": [],
                 "evidence": {"deadline": None, "eligibility": "pour étudiants africains", "funding": None}}
        fake.messages.batches.results_for[job.batch_id] = [_succeeded(job.id, draft)]
        assert batch.collect_results(db)["faits"] == 1
        rev = db.query(AIJob).filter(AIJob.kind == "review", AIJob.status == "en_attente").one()
        assert "date limite manquante" in "; ".join(rev.context["reasons"]) and "niveau" in "; ".join(rev.context["reasons"])
        assert db.query(SeenPage).filter_by(url=url).one().outcome == "en_attente"
        assert not db.query(Scholarship).filter_by(title="Bourse à relire Allemagne").first()  # pas encore enregistrée

        batch.submit_pending(db)
        sent = {r["custom_id"]: r for r in fake.messages.batches.created[-1]}
        assert sent[f"job-{rev.id}"]["params"]["model"] == ai_on.review_model_name  # relecture par le modèle principal
        corrections = {"is_scholarship": True, "corrections": [
            {"field": "deadline", "value_json": '"2027-04-30"'}, {"field": "levels", "value_json": '["BAC5"]'}]}
        db.refresh(rev)
        fake.messages.batches.results_for[rev.batch_id] = [_succeeded(rev.id, corrections)]
        assert batch.collect_results(db)["faits"] == 1
        s = db.query(Scholarship).filter_by(title="Bourse à relire Allemagne").one()
        assert s.deadline == date(2027, 4, 30) and s.levels == ["BAC5"]
        assert db.query(SeenPage).filter_by(url=url).one().outcome == "fiche"
    finally:
        db.close()


def test_haiku_priced_separately():
    from app.ai import costs

    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0, server_tool_use=None)
    cheap, main = costs.estimate(usage, "claude-haiku-5-5")["cost_usd"], costs.estimate(usage, "claude-opus-5-5")["cost_usd"]
    assert cheap < main / 20


def _draft(**kw):
    d = {"is_scholarship": True, "kind": "bourse", "official_link": None, "event_start": None, "event_end": None, "city": None,
         "remote": False, "duration": None, "eligibility": [], "application_steps": [], "title": "Bourse immédiate",
         "organization": "Org", "summary": "Résumé.", "levels": ["BAC5"], "study_countries": [], "eligible_nationalities": ["ALL"],
         "domains": ["tous"], "languages": [], "amount": None, "currency": None, "amount_period": None, "coverage": [],
         "full_funding": False, "deadline": None, "max_age": None, "requirements": [], "target_groups": [],
         "evidence": {"deadline": None, "eligibility": None, "funding": None}}
    d.update(kw)
    return d


def test_immediate_two_step_extraction(monkeypatch, ai_on):
    """Sans lot : premier passage sur le modèle économique, relecture par le modèle principal seulement si douteux."""
    from app.scrapers import extract as ex

    calls = []

    def fake_ask(system, user, schema, **kw):
        calls.append(kw.get("model"))
        if schema is ex.REVIEW_SCHEMA:
            return {"is_scholarship": True, "corrections": [{"field": "deadline", "value_json": '"2027-05-01"'}]}
        return _draft()

    monkeypatch.setattr(ex, "ask_json", fake_ask)
    html = PAGE.format(n=10, body="Bourse de master. Deadline: 1 May 2027.")
    rec = ex.extract(html, "https://officiel.example.org/x", use_ai=True)
    assert calls == [ai_on.extract_model, ai_on.review_model_name] and rec["deadline"] == date(2027, 5, 1)
    assert "evidence" not in rec  # la preuve sert au contrôle, elle n'est pas enregistrée

    calls.clear()
    clean = PAGE.format(n=11, body="Bourse de master sans date annoncée.")
    ex.extract(clean, "https://officiel.example.org/y", use_ai=True)
    assert calls == [ai_on.extract_model]  # fiche sûre : aucune relecture payée


def test_ollama_first_pass(monkeypatch, ai_on):
    """EXTRACT_PROVIDER=ollama : premier passage par le modèle local, sans appel à Claude."""
    import httpx

    from app.scrapers import extract as ex

    monkeypatch.setattr(ai_on, "extract_provider", "ollama")
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"], seen["model"] = url, json["model"]
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req, json={"message": {"content": __import__("json").dumps(_draft(title="Bourse locale"))}})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(ex, "ask_json", lambda *a, **k: pytest.fail("pas de Claude pour une fiche sûre"))
    rec = ex.extract(PAGE.format(n=12, body="Bourse sans date."), "https://officiel.example.org/z", use_ai=True)
    assert rec["title"] == "Bourse locale" and seen["url"].endswith("/api/chat") and seen["model"] == ai_on.ollama_model


def test_questionnaire_asks_gender_and_opens_women_only_offers(client):
    """Le sexe (facultatif) est demandé à l'étape 1 ; une femme voit les offres réservées aux femmes."""
    from app.matching import Criteria

    step1 = client.get("/api/questionnaire").json()["steps"][0]
    q = next(x for x in step1["questions"] if x["id"] == "gender")
    assert q["required"] is False and {o["value"] for o in q["options"]} == {"f", "m"}
    assert "femmes" in Criteria(gender="f").groups() and "femmes" not in Criteria(gender="m").groups()
