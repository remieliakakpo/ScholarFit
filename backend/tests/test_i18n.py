"""Site en anglais : ?lang=en (ou cookie sf_lang=en) traduit les textes servis par l'API."""
import re

DASH = "—"


def _eiffel(client, **params):
    items = client.get("/api/scholarships", params={"q": "eiffel", "include_expired": True, **params}).json()["items"]
    return items[0]


def test_default_stays_french(client):
    s = _eiffel(client)
    assert s["title"] == "Bourse d'excellence Eiffel" and s["kind_label"] == "Bourse d'études"
    assert any(n.startswith("Niveau financé") for n in s["eligibility_notes"])


def test_scholarship_in_english(client):
    s = _eiffel(client, lang="en")
    assert s["title"] == "Eiffel Excellence Scholarship" and s["kind_label"] == "Scholarship"
    assert s["summary"].startswith("Funds outstanding")
    notes = " ".join(s["eligibility_notes"])
    assert "Funded level" in notes and "Study in: France" in notes and "contact the international relations office" in notes
    assert all(d["label"] and not re.search(r"[éèà]", d["label"]) for d in s["documents"])
    assert s["application_steps"][0].startswith("Read the full call")
    assert re.match(r"(Deadline|Urgent|Closes|Applications closed|Applications expected|Deadline passed|Deadline not published)", s["deadline_label"])
    detail = client.get(f"/api/scholarships/{s['slug']}", params={"lang": "en"}).json()
    assert detail["title"] == "Eiffel Excellence Scholarship"


def test_cookie_selects_english(client):
    client.cookies.set("sf_lang", "en")
    try:
        assert _eiffel(client)["kind_label"] == "Scholarship"
    finally:
        client.cookies.clear()
    assert _eiffel(client)["kind_label"] == "Bourse d'études"


def test_meta_questionnaire_offers_in_english(client):
    m = client.get("/api/meta", params={"lang": "en"}).json()
    assert m["levels"]["BAC5"] == "Master's degree" and m["domains"]["informatique"].startswith("Computer science")
    assert m["countries"]["GH"] == "Ghana" and m["countries"]["DE"] == "Germany" and m["regions"]["afrique"] == "Africa"
    assert m["requirements"]["lettre"] == "Cover letter" and m["coverage"]["voyage"] == "flights"
    q = client.get("/api/questionnaire", params={"lang": "en"}).json()["steps"]
    assert q[0]["title"] == "About you" and q[1]["questions"][0]["label"] == "Your current level"
    o = client.get("/api/offres", params={"lang": "en"}).json()
    assert o[0]["name"] == "I apply on my own" and o[0]["price_label"] == "Free"
    stats = client.get("/api/stats/countries", params={"lang": "en"}).json()
    assert any(r["name"] == "Germany" for r in stats)


def test_matching_and_chat_in_english(client, demo):
    r = client.get("/api/matches", headers=demo, params={"lang": "en"}).json()
    reasons = " ".join(x for m in r["items"] for x in m["reasons"] + m["gaps"])
    assert reasons and not re.search(r"\b(votre|elle|date limite)\b", reasons)
    r = client.post("/api/chat", params={"lang": "en"}, json={"messages": [{"role": "user", "content": "I want a master's degree"}]}).json()
    assert r["reply"].startswith("Here is what I understood") and "nationality" in r["reply"]


def test_no_em_dash_in_english(client):
    s = _eiffel(client, lang="en")
    text = " ".join([s["title"], s["summary"], s["deadline_label"], *s["eligibility_notes"], *s["application_steps"]])
    assert DASH not in text
