"""CV, lettres, compatibilité, dossiers payants et exports (mode hors-ligne)."""
import re
from datetime import date

from tests.conftest import register, login

CV = """Awa Diop
awa.diop@mail.com | +221 77 123 45 67 | Dakar
FORMATION
2022-2025 Licence d'informatique, UCAD
2019 Baccalauréat S, Lycée Blaise Diagne
EXPÉRIENCES
Sept 2024 – Déc 2024 Stagiaire développeuse, Orange Digital Center
- Responsable de la refonte du site interne
- Développement d'une application mobile pour 300 utilisateurs
ENGAGEMENT
Bénévole à l'association Jeunes Codeurs, cours de code à 40 collégiens
COMPÉTENCES
Python, JavaScript, SQL
LANGUES
Français, anglais B2"""


def _student(client, email):
    h = register(client, email)
    r = client.put("/api/profile", headers=h, json={
        "full_name": "Awa Diop", "phone": "+221 77 123 45 67", "city": "Dakar", "residence_country": "SN", "gender": "f",
        "nationalities": ["SN"], "birth_date": str(date(date.today().year - 24, 3, 4)), "current_level": "BAC3",
        "target_level": "BAC5", "domain": "informatique", "institution": "Université Cheikh Anta Diop",
        "project": "Je veux créer des outils numériques pour les centres de santé ruraux.",
    })
    assert r.status_code == 200, r.text
    files = {"file": ("cv.txt", CV.encode(), "text/plain")}
    assert client.post("/api/profile/cv", headers=h, files=files).status_code == 200
    return h


def _first(client, q):
    return client.get("/api/scholarships", params={"q": q, "include_expired": True}).json()["items"][0]


def test_cv_diagnostic_criteria(client):
    h = _student(client, "diag@example.org")
    s = _first(client, "daad")
    r = client.post("/api/cv/review", headers=h, json={"scholarship_id": s["id"]})
    out = r.json()
    assert r.status_code == 200, r.text
    keys = {c["key"] for c in out["criteria"]}
    assert {"coordonnees", "structure", "verbes_action", "resultats", "langues", "adequation"} <= keys
    assert 0 <= out["score"] <= 100 and out["verdict"]
    assert any(rw["proposal"].startswith("Piloté la refonte") for rw in out["rewrites"])


def test_adapted_cv_format_and_export(client):
    h = _student(client, "cvadapt@example.org")
    s = _first(client, "daad")
    r = client.post("/api/cv/adapt", headers=h, json={"scholarship_id": s["id"]})
    assert r.status_code == 200, r.text
    cv = r.json()["document"]["data"]
    assert cv["format"] in ("lebenslauf", "europass", "ats", "us_resume", "uk_cv", "francais", "academique")
    lines = [b for sec in cv["sections"] for e in sec["entries"] for b in e["bullets"]] + [i for sec in cv["sections"] for i in sec["items"]]
    assert lines and all("—" not in x and "[" not in x for x in lines)
    assert any(b.startswith("Piloté la refonte") for b in lines)
    pdf = client.post("/api/export/cv", headers=h, params={"fmt": "pdf"}, json={"data": cv})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    docx = client.post("/api/export/cv", headers=h, params={"fmt": "docx"}, json={"data": cv})
    assert docx.status_code == 200 and docx.content[:2] == b"PK"


def test_letter_clean_and_paid_second_pack(client, admin):
    h = _student(client, "lettre@example.org")
    s1, s2 = _first(client, "daad"), _first(client, "eiffel")
    body = {"scholarship_id": s1["id"], "language": "fr", "why_country": "parce que les universités allemandes sont en avance sur la santé numérique",
            "project_after": "je compte rentrer à Dakar pour créer un service de suivi des vaccinations", "max_words": 400}
    r = client.post("/api/letters", headers=h, json=body)
    assert r.status_code == 200, r.text
    letter = r.json()["document"]["data"]
    assert letter["salutation"] == "Madame, Monsieur,"
    assert letter["subject"].startswith("Objet : candidature")
    for para in letter["paragraphs"]:
        assert para[-1] in ".!?", para
        assert ":" not in para and "—" not in para and "[" not in para and "(e)" not in para
    assert r.json()["word_count"] <= 400
    # Relance dans le même dossier : gratuite
    assert client.post("/api/letters", headers=h, json=body).status_code == 200
    # Dossier pour une autre bourse : abonnement mensuel après le dossier offert
    r = client.post("/api/letters", headers=h, json={**body, "scholarship_id": s2["id"]})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "abonnement_requis"
    o = client.post("/api/credits/orders", headers=h, json={"method": "flooz", "reference": "TX123"}).json()
    assert o["status"] == "en_verification" and o["amount"] == 2500
    assert client.patch(f"/api/admin/credit-orders/{o['id']}", headers=h, json={"status": "paye"}).status_code == 403
    assert client.patch(f"/api/admin/credit-orders/{o['id']}", headers=admin, json={"status": "paye"}).status_code == 200
    r = client.post("/api/letters", headers=h, json={**body, "scholarship_id": s2["id"]})
    assert r.status_code == 200, r.text
    c = client.get("/api/credits", headers=h).json()
    assert c["subscription"]["active"] and c["subscription"]["used_this_period"] == 1
    assert c["available"] == c["subscription"]["monthly_packs"] - 1
    # Limite mensuelle de l'abonnement (maîtrise du coût de l'IA)
    from app.config import get_settings
    st = get_settings()
    old = st.subscription_monthly_packs
    st.subscription_monthly_packs = 1
    try:
        s3 = _first(client, "chevening")
        r = client.post("/api/letters", headers=h, json={**body, "scholarship_id": s3["id"]})
        assert r.status_code == 402 and r.json()["detail"]["code"] == "limite_mensuelle"
    finally:
        st.subscription_monthly_packs = old
    pdf = client.post("/api/export/lettre", headers=h, params={"fmt": "pdf"}, json={"data": letter})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_english_letter_layout(client):
    h = _student(client, "english@example.org")
    s = _first(client, "daad")
    r = client.post("/api/letters", headers=h, json={"scholarship_id": s["id"], "language": "en", "max_words": 400})
    assert r.status_code == 200, r.text
    letter = r.json()["document"]["data"]
    assert letter["salutation"].startswith("Dear")
    assert letter["closing"] in ("Yours sincerely,", "Sincerely,")
    assert re.match(r"^(\d{1,2} [A-Z][a-z]+ \d{4}|[A-Z][a-z]+ \d{1,2}, \d{4})$", letter["place_date"])


def test_letter_requires_header_information(client):
    h = register(client, "vide@example.org")
    s = _first(client, "daad")
    ctx = client.get(f"/api/letters/{s['id']}/context", headers=h).json()
    assert {m["field"] for m in ctx["missing"]} >= {"full_name", "phone", "city", "cv"}
    assert client.post("/api/letters", headers=h, json={"scholarship_id": s["id"]}).status_code == 422


def test_fit_check(client):
    h = _student(client, "fit@example.org")
    s = _first(client, "daad")
    r = client.get(f"/api/scholarships/{s['id']}/fit", headers=h)
    out = r.json()
    assert r.status_code == 200, r.text
    assert out["verdict"] and 0 <= out["score"] <= 100
    assert out["checks"] and out["documents"]
    assert any(d["key"] == "cv" and d["ready"] for d in out["documents"])


def test_ai_paths_are_cleaned(monkeypatch):
    """Chemins IA simulés : la sortie est nettoyée (tirets, crochets, deux-points) et la lettre est réécrite si besoin."""
    from app.ai import cv as cvmod
    from app.ai import letter as lmod
    from app.models import Profile, Scholarship

    p = Profile(full_name="Awa Diop", phone="+221", city="Dakar", residence_country="SN", target_level="BAC5", domain="informatique", cv_text=CV, gender="f")
    s = Scholarship(id=9, title="Bourse Test", organization="Fondation X", summary="Leadership et impact.", study_countries=["DE"], languages=["fr"],
                    eligibility=[], target_groups=[], language_tests={}, levels=["BAC5"], domains=["tous"], requirements=["cv", "lettre"])

    def fake_cv(system, user, schema, **kw):
        return {"headline": "Master en informatique", "summary": "Développeuse orientée santé numérique — trois ans de projets.",
                "sections": [{"key": "experience", "kind": "entries", "entries": [{"title": "Stagiaire", "organization": "ODC", "location": "Dakar",
                              "dates": "2024", "bullets": ["Conçu une application — 300 utilisateurs.", "Ajouté [chiffre]"]}], "items": []}],
                "changes": ["Format adapté"]}
    monkeypatch.setattr(cvmod, "ask_json", fake_cv)
    out = cvmod.build_cv(CV, p, s, "a@b.c", use_ai=True)
    bullets = out["sections"][0]["entries"][0]["bullets"]
    assert bullets == ["Conçu une application, 300 utilisateurs"]
    assert "—" not in out["summary"]

    calls = []

    def fake_letter(system, user, schema, **kw):
        calls.append(user)
        if len(calls) == 1:
            return {"paragraphs": ["Je suis passionnée par le code : depuis toujours", "Deuxième.", "Troisième."]}
        return {"paragraphs": ["J'ai conçu une application utilisée par 300 patients.", "Je vise ce master à Heidelberg.", "Je reste disponible pour un entretien."]}
    monkeypatch.setattr(lmod, "ask_json", fake_letter)
    L = lmod.generate_letter(p, s, {}, "fr", 400, "sobre", use_ai=True, email="a@b.c")
    assert len(calls) == 2 and "CORRIGEZ" in calls[1]
    assert L["paragraphs"][0].startswith("J'ai conçu") and L["ai_used"]


ATS_CV = """KOFI MENSAH
ANALYSTE RÉSEAUX | SÉCURITÉ DES SYSTÈMES | SOC
Accra, Ghana  |  +233 20 000 0000  |  kofi@example.org  |  LinkedIn
Disponible dès octobre 2026 pour un CDI ou un CDD  |  Mobilité : Afrique et Europe
PROFIL PROFESSIONNEL
Titulaire d'un Master en Informatique, j'ai une expérience pratique en sécurité des réseaux. Je
souhaite contribuer à des missions de supervision au sein d'une entreprise.
COMPÉTENCES TECHNIQUES
Sécurité & supervision : Snort, Wireshark, Nmap, OWASP
ZAP
Systèmes & réseaux : Windows, Ubuntu, TCP/IP
EXPÉRIENCES PROFESSIONNELLES
Stagiaire en cybersécurité | Net Lab | À distance | Inde Fév. 2026 - Mars 2026
• Analyse de vulnérabilités Web avec Nmap et OWASP ZAP ;
rédaction de rapports techniques.
Technicien réseaux | Data Co | Accra, Ghana
• Configuration de routeurs et points d'accès sans fil.
FORMATION
Master en Informatique | Université d'Accra 2024 - 2026
Licence Réseaux | Université d'Accra /
École d'ingénieurs
2021 - 2024
LANGUES
Français : courant   |   Anglais : intermédiaire
Sept. 2023 - Avr. 2024"""


def test_cv_follows_ats_model_and_drops_job_mentions():
    from app.ai.cv import build_cv_rules
    from app.models import Profile, Scholarship

    p = Profile(full_name="Kofi Mensah", residence_country="GH", city="Accra", target_level="BAC5", domain="informatique",
                project="Après le master, je compte enseigner la sécurité informatique à Accra.")
    s = Scholarship(id=1, title="Bourse d'excellence Eiffel", organization="Campus France", summary="Master en France", study_countries=["FR"],
                    languages=["fr"], eligibility=[], levels=["BAC5"], domains=["tous"], deadline=date(2027, 1, 8))
    cv = build_cv_rules(ATS_CV, p, s, "kofi@example.org")
    keys = [sec["key"] for sec in cv["sections"]]
    assert keys.index("skills") < keys.index("experience") < keys.index("education") < keys.index("languages")
    h = cv["header"]
    assert "Sécurité des systèmes" in h["headline"] and h["objective"].startswith("Candidature : Bourse d'excellence Eiffel | Rentrée 2027")
    exp = next(sec for sec in cv["sections"] if sec["key"] == "experience")["entries"]
    first = next(e for e in exp if e["organization"] == "Net Lab")
    assert first["title"] == "Stagiaire en cybersécurité" and first["location"] == "À distance, Inde"
    assert "rédaction de rapports" in first["bullets"][0]  # ligne coupée par le PDF recollée
    assert next(e for e in exp if e["organization"] == "Data Co")["dates"] == "Sept. 2023 - Avr. 2024"  # date détachée rendue
    skills = next(sec for sec in cv["sections"] if sec["key"] == "skills")["items"]
    assert skills[0].endswith("OWASP ZAP")
    edu = next(sec for sec in cv["sections"] if sec["key"] == "education")["entries"]
    assert any(e["organization"] == "Université d'Accra / École d'ingénieurs" and e["dates"] == "2021 - 2024" for e in edu)
    assert next(sec for sec in cv["sections"] if sec["key"] == "languages")["items"] == ["Français : courant | Anglais : intermédiaire"]
    text = (cv["summary"] + " " + h["objective"] + " " + h["headline"]).lower()
    assert "cdi" not in text and "cdd" not in text and "missions" not in text
    assert "bourse d'excellence eiffel" in text and "en france" in text and "enseigner la sécurité" in text
