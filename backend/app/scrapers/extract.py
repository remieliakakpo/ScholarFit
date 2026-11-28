"""Transforme une page HTML en fiche de bourse structurée.

Avec une clé API, Claude lit le texte libre et remplit un schéma JSON strict. Sans clé,
une extraction par règles récupère le titre, la date limite, le montant et les niveaux.
Dans les deux cas la fiche est marquée « à vérifier » tant qu'un humain ne l'a pas validée.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from urllib.parse import urljoin, urlparse

from ..ai.client import ask_json
from ..vocab import DOMAINS, KINDS, LEVELS

MONTHS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
MONTHS_EN = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}


def html_to_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        tag.decompose()
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True)
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    return title, text[:20000]


APPLY_WORDS = re.compile(r"(postuler|candidater|candidature|site officiel|lien officiel|apply|application|official|website|register|inscription|s'inscrire|plus d'informations|more information|cliquez ici|click here)", re.I)
SKIP_HOSTS = ("facebook.", "twitter.", "x.com", "linkedin.", "whatsapp.", "t.me", "telegram.", "instagram.", "youtube.",
              "pinterest.", "google.", "bit.ly", "wa.me", "tiktok.")


def official_link(html: str, page_url: str) -> str | None:
    """Sur une page d'agrégateur (ex. Afri-Carrières), retrouve le lien vers le site officiel de l'organisme :
    lien externe dont le texte (ou le texte qui le précède) parle de postuler ou du site officiel."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    host = urlparse(page_url).netloc.removeprefix("www.")
    best: tuple[int, str] | None = None
    for i, a in enumerate(main.find_all("a", href=True)):
        href = urljoin(page_url, a["href"])
        h = urlparse(href)
        if h.scheme not in ("http", "https") or h.netloc.removeprefix("www.") == host:
            continue
        if any(x in h.netloc for x in SKIP_HOSTS):
            continue
        context = a.get_text(" ", strip=True) + " " + (a.find_previous(string=True) or "")
        score = (10 if APPLY_WORDS.search(context) else 0) - i * 0.01
        if best is None or score > best[0]:
            best = (score, href)
    return best[1] if best and best[0] > 0 else None


def find_deadline(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    t = text.lower()
    candidates: list[date] = []
    window = []
    for m in re.finditer(r"(date limite|deadline|clôture|cloture|avant le|jusqu'au|until|closing date)", t):
        window.append(t[m.start(): m.start() + 120])
    zones = window or [t]
    for z in zones:
        for d, mo, y in re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", z):
            try:
                candidates.append(date(int(y), int(mo), int(d)))
            except ValueError:
                pass
        for d, mo, y in re.findall(r"\b(\d{1,2})(?:er)?\s+(" + "|".join(MONTHS_FR) + r")\s+(20\d{2})", z):
            candidates.append(date(int(y), MONTHS_FR[mo], int(d)))
        for d, mo, y in re.findall(r"\b(\d{1,2})\s+(" + "|".join(MONTHS_EN) + r")\s+(20\d{2})", z):
            candidates.append(date(int(y), MONTHS_EN[mo], int(d)))
        for mo, d, y in re.findall(r"\b(" + "|".join(MONTHS_EN) + r")\s+(\d{1,2}),?\s+(20\d{2})", z):
            candidates.append(date(int(y), MONTHS_EN[mo], int(d)))
        if candidates:
            break
    future = [c for c in candidates if c >= today]
    return min(future) if future else (max(candidates) if candidates else None)


def find_amount(text: str) -> tuple[float | None, str | None, str | None]:
    m = re.search(r"(\d[\d\s.,]{1,9})\s*(€|eur|euros|\$|usd|£|gbp|chf|cad|fcfa)\s*(?:par|per|/)?\s*(mois|month|an|année|year)?", text, re.I)
    if not m:
        return None, None, None
    raw = re.sub(r"[\s.](?=\d{3}\b)", "", m.group(1)).replace(",", ".").strip()
    try:
        amount = float(raw)
    except ValueError:
        return None, None, None
    cur = {"€": "EUR", "eur": "EUR", "euros": "EUR", "$": "USD", "usd": "USD", "£": "GBP", "gbp": "GBP", "chf": "CHF", "cad": "CAD", "fcfa": "XOF"}[m.group(2).lower()]
    period = {"mois": "mois", "month": "mois", "an": "an", "année": "an", "year": "an"}.get((m.group(3) or "").lower(), "total")
    return amount, cur, period


def find_levels(text: str) -> list[str]:
    t = text.lower()
    levels = []
    if re.search(r"licence|bachelor|undergraduate|premier cycle", t):
        levels.append("BAC3")
    if re.search(r"master|graduate|deuxième cycle|msc|mba", t):
        levels.append("BAC5")
    if re.search(r"doctorat|doctoral|phd|ph\.d|post-?doc|thèse", t):
        levels.append("BAC7")
    return levels


def extract_rules(title: str, text: str, url: str) -> dict:
    from .collector import guess_kind

    amount, currency, period = find_amount(text)
    first_par = next((p for p in text.split("\n") if len(p) > 80), text[:300])
    return {
        "kind": guess_kind(title + " " + text[:1500]),
        "title": title[:300] or url,
        "organization": "",
        "official_url": url,
        "summary": first_par[:600],
        "levels": find_levels(text),
        "deadline": find_deadline(text),
        "amount": amount,
        "currency": currency,
        "amount_period": period,
        "full_funding": bool(re.search(r"(entièrement financ|fully funded|full scholarship|couvre (tous )?les frais)", text, re.I)),
    }


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_scholarship": {"type": "boolean"},
        # Preuves (idée reprise d'Opportia) : phrase recopiée telle quelle de la page pour les champs
        # qui comptent le plus. Vérifiées sans IA : une preuve introuvable déclenche la relecture.
        "evidence": {
            "type": "object",
            "properties": {
                "deadline": {"type": ["string", "null"]},
                "eligibility": {"type": ["string", "null"]},
                "funding": {"type": ["string", "null"]},
            },
            "required": ["deadline", "eligibility", "funding"],
            "additionalProperties": False,
        },
        "kind": {"type": "string", "enum": list(KINDS)},
        "title": {"type": "string"},
        "official_link": {"type": ["string", "null"]},
        "event_start": {"type": ["string", "null"]},
        "event_end": {"type": ["string", "null"]},
        "city": {"type": ["string", "null"]},
        "remote": {"type": "boolean"},
        "duration": {"type": ["string", "null"]},
        "eligibility": {"type": "array", "items": {"type": "string"}},
        "application_steps": {"type": "array", "items": {"type": "string"}},
        "organization": {"type": "string"},
        "summary": {"type": "string"},
        "levels": {"type": "array", "items": {"type": "string", "enum": list(LEVELS)}},
        "study_countries": {"type": "array", "items": {"type": "string"}},
        "eligible_nationalities": {"type": "array", "items": {"type": "string"}},
        "domains": {"type": "array", "items": {"type": "string", "enum": list(DOMAINS)}},
        "languages": {"type": "array", "items": {"type": "string"}},
        "amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
        "amount_period": {"type": ["string", "null"], "enum": ["mois", "an", "total", None]},
        "coverage": {"type": "array", "items": {"type": "string", "enum": ["frais", "logement", "voyage", "allocation", "assurance"]}},
        "full_funding": {"type": "boolean"},
        "deadline": {"type": ["string", "null"]},
        "max_age": {"type": ["integer", "null"]},
        "requirements": {"type": "array", "items": {"type": "string", "enum": ["cv", "lettre", "recommandation", "releves", "test_langue", "projet_recherche", "passeport", "diplome"]}},
        "target_groups": {"type": "array", "items": {"type": "string", "enum": ["femmes", "refugie", "handicap", "revenus_modestes", "premiere_generation"]}},
    },
    "required": ["is_scholarship", "evidence", "kind", "official_link", "event_start", "event_end", "city", "remote", "duration",
                 "eligibility", "application_steps", "title", "organization", "summary", "levels", "study_countries", "eligible_nationalities", "domains", "languages", "amount", "currency", "amount_period", "coverage", "full_funding", "deadline", "max_age", "requirements", "target_groups"],
    "additionalProperties": False,
}

EXTRACT_SYSTEM = """Tu transformes le texte d'une page web en fiche d'opportunité pour étudiants. Réponds uniquement avec le JSON.
- is_scholarship = false si la page ne décrit pas UNE opportunité précise pour étudiants ou jeunes diplômés.
  Une offre d'emploi (CDI, CDD, recrutement), un guide (visa, conseils) ou un article de blog n'en sont pas : is_scholarship = false.
- kind : bourse (financement d'études), stage (stage, internship, traineeship), conference (conférence, sommet,
  forum, colloque), formation (formation courte, atelier, bootcamp, training), concours (concours, compétition,
  prix, hackathon, challenge), echange (programme d'échange, école d'été, camp, mobilité), fellowship
  (fellowship, programme de leadership ou de recherche rémunéré), cours_en_ligne (cours en ligne, MOOC, certificat en ligne).
- official_link : adresse complète du site officiel de l'organisme cité dans la page (lien « postuler », « site officiel »), null sinon.
- event_start, event_end : dates de la conférence ou du stage (AAAA-MM-JJ), null si absentes. city : ville. remote : en ligne possible.
- duration : durée du stage en clair (ex. « 3 à 6 mois »). eligibility, application_steps : phrases courtes en français, avec tes mots.
- levels : diplôme financé (BAC3 = licence/bachelor, BAC5 = master, BAC7 = doctorat ou post-doc).
- study_countries, eligible_nationalities : codes ISO alpha-2 ; eligible_nationalities = ["ALL"] si ouvert à tous,
  ou les groupes AFRICA, EU, FRANCOPHONIE, DEVELOPING si la page les cite.
- deadline : prochaine date limite au format AAAA-MM-JJ, null si absente.
- study_countries d'un stage : pays où se déroule le stage.
- target_groups : public réservé si la page le dit (femmes, refugie, handicap, revenus_modestes, premiere_generation), vide sinon.
- domains : ["tous"] si tous les domaines, sinon les domaines cités (informatique, sante, agriculture…).
- summary : deux phrases maximum, reformulées avec tes mots (ne recopie pas le texte).
- evidence : pour la date limite, les conditions et le financement, recopie mot pour mot une courte phrase
  de la page qui les justifie (moins de 200 caractères), null si la page n'en parle pas.
- N'invente rien : laisse vide ou null ce que la page ne dit pas."""

# Champs qu'une relecture peut corriger (mêmes noms que la fiche extraite)
REVIEWABLE = [k for k in EXTRACT_SCHEMA["properties"] if k not in ("evidence",)]

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "is_scholarship": {"type": "boolean"},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": REVIEWABLE},
                    "value_json": {"type": "string"},
                },
                "required": ["field", "value_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["is_scholarship", "corrections"],
    "additionalProperties": False,
}

REVIEW_SYSTEM = """Tu relis une fiche d'opportunité pour étudiants extraite automatiquement d'une page web.
On te donne la page, la fiche et les points douteux. Corrige seulement ce qui est faux ou manquant d'après la page :
ne renvoie que les champs à changer, chacun avec sa nouvelle valeur encodée en JSON dans value_json
(une date : "2027-03-15" avec ses guillemets ; une liste : ["BAC5"] ; une valeur vide : null). Mêmes règles que l'extraction : dates AAAA-MM-JJ, codes ISO
alpha-2, niveaux BAC3/BAC5/BAC7, phrases en français avec tes mots. is_scholarship = false si la page n'est pas
une opportunité précise (une offre d'emploi n'en est pas une). N'invente rien : si la page ne dit pas, mets "null"
ou ne corrige pas. Aucune correction si la fiche est juste."""

_DEADLINE_WORDS = re.compile(r"deadline|date limite|closing date|clôture|apply (?:by|before)|before \d|until \d|jusqu'au", re.I)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w%€$]+", " ", s.lower()).split())


def review_reasons(data: dict, text: str) -> list[str]:
    """Points douteux d'une fiche extraite, vérifiés sans IA. Vide = rien à relire."""
    if not data.get("is_scholarship", True):
        return []
    reasons = []
    if not data.get("title"):
        reasons.append("titre manquant")
    page = _norm(text)
    for field, excerpt in (data.get("evidence") or {}).items():
        if excerpt and _norm(excerpt)[:150] not in page:
            reasons.append(f"preuve introuvable dans la page ({field})")
    evidence = data.get("evidence") or {}
    if data.get("deadline") and not evidence.get("deadline"):
        reasons.append("date limite sans preuve")
    if not data.get("deadline") and _DEADLINE_WORDS.search(text) and _DATE_RE.search(text):
        reasons.append("date limite manquante alors que la page en parle")
    if (data.get("kind") or "bourse") == "bourse" and not data.get("levels"):
        reasons.append("niveau d'études manquant")
    return reasons


def review_prompt(extract_request: str, draft: dict, reasons: list[str]) -> str:
    import json

    shown = {k: v for k, v in draft.items() if k != "evidence"}
    return (f"POINTS DOUTEUX : {'; '.join(reasons)}\n\nFICHE :\n{json.dumps(shown, ensure_ascii=False, default=str)}"
            f"\n\nPAGE :\n{extract_request}")


def apply_review(draft: dict, review: dict | None) -> dict:
    """Fiche corrigée. Une correction illisible est ignorée (on garde la valeur du premier passage)."""
    import json

    out = dict(draft)
    if not review:
        return out
    if review.get("is_scholarship") is False:
        out["is_scholarship"] = False
        return out
    for c in review.get("corrections") or []:
        field = c.get("field")
        if field not in REVIEWABLE or field == "is_scholarship":
            continue
        try:
            out[field] = json.loads(c.get("value_json", "null"))
        except ValueError:
            continue
    return out


def first_pass(title: str, text: str, url: str) -> dict | None:
    """Premier passage : modèle économique (Claude Haiku) ou modèle local (Ollama), selon EXTRACT_PROVIDER."""
    from ..config import get_settings

    s = get_settings()
    prompt = extract_prompt(title, text, url)
    if s.extract_provider == "ollama":
        return ollama_json(EXTRACT_SYSTEM, prompt, EXTRACT_SCHEMA)
    return ask_json(EXTRACT_SYSTEM, prompt, EXTRACT_SCHEMA, effort="low", model=s.extract_model, purpose="extract")


def review(extract_request: str, draft: dict, reasons: list[str]) -> dict:
    """Relecture ciblée par le modèle principal : ne renvoie que les champs à corriger."""
    from ..config import get_settings

    s = get_settings()
    data = ask_json(REVIEW_SYSTEM, review_prompt(extract_request, draft, reasons), REVIEW_SCHEMA, effort="low",
                    max_tokens=4000, model=s.review_model_name, purpose="review")
    return apply_review(draft, data)


def ollama_json(system: str, user: str, schema: dict) -> dict | None:
    """Appel à un modèle local Ollama (gratuit à l'usage, sur une machine à vous). None si indisponible."""
    import json

    import httpx

    from ..config import get_settings

    s = get_settings()
    try:
        r = httpx.post(f"{s.ollama_url.rstrip('/')}/api/chat", timeout=600, json={
            "model": s.ollama_model, "stream": False, "format": schema, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    except (httpx.HTTPError, ValueError, KeyError):
        return None


def extract(html: str, url: str, use_ai: bool = True) -> dict | None:
    """Extraction en deux temps : premier passage économique, contrôle sans IA, relecture ciblée par le
    modèle principal seulement pour les fiches douteuses. Sans IA : extraction par règles."""
    from ..config import get_settings

    title, text = html_to_text(html)
    if use_ai:
        data = first_pass(title, text, url)
        if data is not None:
            reasons = review_reasons(data, text)
            if reasons and get_settings().ai_enabled:
                data = review(extract_prompt(title, text, url), data, reasons)
            return ai_record(data, url)
    return extract_rules(title, text, url)


EXTRACT_MAX_CHARS = 15000


def extract_prompt(title: str, text: str, url: str) -> str:
    return f"URL : {url}\nTitre : {title}\n\n{text[:EXTRACT_MAX_CHARS]}"


def split_prompt(prompt: str) -> tuple[str, str, str]:
    """(titre, texte, adresse) d'une demande faite par extract_prompt (repli par règles d'un lot échoué)."""
    head, _, text = prompt.partition("\n\n")
    lines = head.split("\n")
    url = lines[0].removeprefix("URL : ") if lines else ""
    title = lines[1].removeprefix("Titre : ") if len(lines) > 1 else ""
    return title, text, url


def ai_record(data: dict, url: str) -> dict | None:
    """Fiche à partir de la réponse de l'IA (appel immédiat ou par lot). None : pas une opportunité."""
    data = dict(data)
    data.pop("evidence", None)  # preuves : servent au contrôle, pas enregistrées
    if not data.pop("is_scholarship", True):
        return None
    data["official_url"] = url
    link = data.pop("official_link", None)
    if link and link.startswith("http"):
        data["official_url"] = link
    for k in ("deadline", "event_start", "event_end"):
        if data.get(k):
            try:
                data[k] = date.fromisoformat(data[k])
            except ValueError:
                data[k] = None
    data["domains"] = data.get("domains") or ["tous"]
    data["eligible_nationalities"] = data.get("eligible_nationalities") or ["ALL"]
    return data
