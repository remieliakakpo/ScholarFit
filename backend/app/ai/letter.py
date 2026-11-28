"""Lettre de motivation adaptée à une bourse.

La lettre est rendue sous forme structurée : expéditeur, destinataire, lieu et date, objet,
formule d'appel, paragraphes, formule de politesse, signature. Cette structure sert à
l'aperçu, au PDF et au fichier Word, avec la disposition propre à chaque langue :

- français : coordonnées en haut à gauche, destinataire à droite, « Lomé, le 20 novembre 2026 »,
  « Objet : … », « Madame, Monsieur, », formule de politesse complète ;
- anglais (Royaume-Uni et international) : « 20 November 2026 », « Dear Members of the Selection
  Committee, », « Yours sincerely, » ;
- anglais (États-Unis, Canada) : « November 20, 2026 », « Sincerely, ».

Avant d'être rendue, la lettre passe un contrôle : pas de tiret cadratin, pas de deux-points dans
le corps, pas de phrase en suspens, pas de crochets, pas de formule stéréotypée.
"""
from __future__ import annotations

import re
from datetime import date

from ..i18n import is_en, t
from ..models import Profile, Scholarship
from ..vocab import DOMAINS
from . import style, writing
from .client import ask_json
from .cv import ACTION_VERBS_EN, ACTION_VERBS_FR, EN_MONTHS, FR_MONTHS, THEMES, _clean_line, _object_after, apply_weak_start, detect_themes
from .documents import split_sections
from .formats import a_bourse_fr, bourse_name_en, bourse_name_fr, country_name, domain_name, letter_style, offered_fr, short_title

QUESTIONS_EN = {
    "target_program": "Programme or university you are aiming for",
    "why_country": "Why this country",
    "why_program": "Why this programme and this scholarship",
    "study_plan": "Your study plan",
    "project_after": "Your plans after your studies",
    "proud_of": "A notable achievement",
    "extra": "Anything else you want the panel to know",
}
READINESS_EN = {
    "full_name": "Full name", "phone": "Phone", "city": "City of residence", "residence_country": "Country of residence",
    "email": "Email", "domain": "Field of study", "target_level": "Target degree", "cv": "Imported CV",
}


def question_label(key: str, label: str) -> str:
    return QUESTIONS_EN.get(key, label) if is_en() else label


QUESTIONS = [
    ("target_program", "Programme ou université visés"),
    ("why_country", "Pourquoi ce pays"),
    ("why_program", "Pourquoi ce programme et cette bourse"),
    ("study_plan", "Votre plan d'études"),
    ("project_after", "Votre projet après les études"),
    ("proud_of", "Une réalisation marquante"),
    ("extra", "Ce que vous tenez à dire au jury"),
]

LEVEL_PHRASE = {
    "fr": {"BAC": "une licence", "BAC3": "une licence", "BAC5": "un master", "BAC7": "un doctorat"},
    "en": {"BAC": "an undergraduate degree", "BAC3": "a bachelor's degree", "BAC5": "a master's degree", "BAC7": "a PhD"},
}
CURRENT_PHRASE = {
    "fr": {"BAC": "le baccalauréat", "BAC3": "ma licence", "BAC5": "mon master", "BAC7": "mon doctorat"},
    "en": {"BAC": "secondary school", "BAC3": "my bachelor's degree", "BAC5": "my master's degree", "BAC7": "my doctorate"},
}


# ------------------------------------------------------------------ en-tête
def _date_text(style: str, today: date) -> str:
    if style == "fr":
        day = "1er" if today.day == 1 else str(today.day)
        return f"{day} {FR_MONTHS[today.month - 1]} {today.year}"
    if style == "en_us":
        return f"{EN_MONTHS[today.month - 1]} {today.day}, {today.year}"
    return f"{today.day} {EN_MONTHS[today.month - 1]} {today.year}"


def build_header(p: Profile, s: Scholarship, email: str | None, language: str, answers: dict, today: date | None = None) -> dict:
    today = today or date.today()
    style = letter_style(s, language)
    country = country_name(p.residence_country, language) if p.residence_country else ""
    sender = [p.full_name or ""]
    if p.address:
        sender.append(p.address)
    city_line = ", ".join(x for x in [p.city, country] if x)
    if city_line:
        sender.append(city_line)
    if p.phone:
        sender.append(p.phone)
    if email:
        sender.append(email)
    if style == "fr":
        recipient = ["Comité de sélection", s.organization]
    else:
        # Organisme au nom français dans la fiche : le nom (traduit) de la bourse le remplace dans une lettre anglaise
        recipient = ["Selection Committee", s.organization if s.organization and not _FR_ORG.search(s.organization) else short_title(s, "en")]
    if answers.get("recipient_address"):
        recipient += [l.strip() for l in answers["recipient_address"].splitlines() if l.strip()]
    dt = _date_text(style, today)
    place_date = (f"{p.city}, le {dt}" if p.city else f"Le {dt}") if style == "fr" else dt
    program = (answers.get("target_program") or "").strip().rstrip(".")
    if style == "fr":
        subject = f"Objet : candidature {a_bourse_fr(s)}" + (f", {program}" if program else "")
        salutation = "Madame, Monsieur,"
        closing = "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées."
    else:
        subject = f"Application for {bourse_name_en(s)}" + (f", {program}" if program else "")
        salutation = "Dear Members of the Selection Committee,"
        closing = "Sincerely," if style == "en_us" else "Yours sincerely,"
    return {
        "language": language, "style": style, "sender": [x for x in sender if x], "recipient": [x for x in recipient if x],
        "place_date": place_date, "subject": subject, "salutation": salutation, "closing": closing,
        "signature": p.full_name or "",
    }


# ------------------------------------------------------------------ lecture du CV pour la lettre
def cv_highlights(cv_text: str | None, language: str, limit: int = 2) -> list[str]:
    """Lignes d'expérience qui commencent (ou peuvent commencer) par un verbe d'action, dans la bonne langue."""
    if not cv_text:
        return []
    verbs = ACTION_VERBS_EN if language == "en" else ACTION_VERBS_FR
    sections = split_sections(cv_text)
    lines = []
    for key in ("experiences", "engagement", "projets", "recherche"):
        for raw in sections.get(key, "").splitlines():
            line = _clean_line(raw)
            line = apply_weak_start(line) or line
            low = line.lower()
            if len(line.split()) < 4 or len(line.split()) > 28 or "[" in line:
                continue
            if any(re.match(rf"{re.escape(v)}\b", low) for v in verbs):
                lines.append(line.rstrip(". "))
    # On privilégie les lignes chiffrées
    lines.sort(key=lambda l: 0 if re.search(r"\d", l) else 1)
    return lines[:limit]


def at_institution(name: str, language: str) -> str:
    if language == "en":
        return f"at {name}"
    low = name.lower()
    if low.startswith(("université", "universite", "école", "ecole", "institut", "académie", "université")):
        return f"à l'{name}"
    if low.startswith(("lycée", "collège", "complexe", "centre", "groupe")):
        return f"au {name}"
    return f"à {name}"


def _num(x: float, language: str) -> str:
    t = f"{x:g}"
    return t if language == "en" else t.replace(".", ",")


def _join_actions(items: list[str], language: str) -> str:
    items = [writing.lower_first(i) for i in items]
    if language == "en":
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def _integrate(answer: str, lead: str, fragment_prefix: str, language: str) -> str:
    """Insère une réponse libre : phrase autonome après une phrase d'appui, ou suite directe si c'est un fragment."""
    a = (answer or "").strip()
    if not a:
        return ""
    low = a.lower()
    connectors = ("parce que", "parce qu'", "car ", "pour ", "afin de", "because", "since ", "to ")
    if low.startswith(connectors):
        return writing.complete_sentence(f"{fragment_prefix} {writing.lower_first(a)}")
    sentences = writing.as_sentences(a)
    return f"{lead} {sentences}".strip() if lead else sentences


# ------------------------------------------------------------------ parcours tiré du CV
_MONTHS_IN = {"jan": 1, "janv": 1, "janvier": 1, "january": 1, "fév": 2, "fev": 2, "févr": 2, "fevr": 2, "février": 2, "fevrier": 2, "feb": 2, "february": 2,
              "mars": 3, "mar": 3, "march": 3, "avr": 4, "avril": 4, "apr": 4, "april": 4, "mai": 5, "may": 5, "juin": 6, "jun": 6, "june": 6,
              "juil": 7, "juillet": 7, "jul": 7, "july": 7, "août": 8, "aout": 8, "aug": 8, "august": 8, "sept": 9, "sep": 9, "septembre": 9, "september": 9,
              "oct": 10, "octobre": 10, "october": 10, "nov": 11, "novembre": 11, "november": 11, "déc": 12, "dec": 12, "décembre": 12, "decembre": 12, "december": 12}
_ONGOING = re.compile(r"aujourd|présent|present|en cours|current|now|ce jour|actuel", re.I)


def _point(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"(?:([A-Za-zéûÉ]+)\.?\s+|(\d{1,2})/)?((?:19|20)\d\d)", text)
    if not m:
        return None, None
    month = None
    if m.group(1):
        month = _MONTHS_IN.get(m.group(1).lower().rstrip("."))
    elif m.group(2):
        month = int(m.group(2)) if 1 <= int(m.group(2)) <= 12 else None
    return month, int(m.group(3))


def parse_range(dates: str) -> dict:
    """« Avr. 2023 - Avr. 2026 » → début, fin, en cours ; tolère « 2024 - 2026 » et « 2022 - présent »."""
    d = (dates or "").strip()
    parts = re.split(r"\s+[-–—à]\s+|\s*[-–—]\s*(?=[A-Za-zÀ-ÿ]+\.?\s+\d|\d{4}|aujourd|présent|present|en cours|now)", d, maxsplit=1)
    sm, sy = _point(parts[0]) if parts else (None, None)
    em, ey = (_point(parts[1]) if len(parts) > 1 else (None, None))
    ongoing = bool(_ONGOING.search(d)) or (len(parts) > 1 and ey is None and sy is not None)
    if len(parts) == 1:
        em, ey = sm, sy
    return {"sm": sm, "sy": sy, "em": em, "ey": ey, "ongoing": ongoing}


def _when(month: int | None, year: int | None, language: str) -> str:
    if not year:
        return ""
    if month:
        return f"{EN_MONTHS[month - 1]} {year}" if language == "en" else f"{FR_MONTHS[month - 1]} {year}"
    return str(year)


def _finished(r: dict, today: date) -> bool:
    if r["ongoing"] or not r["ey"]:
        return False
    if r["em"]:
        return (r["ey"], r["em"]) <= (today.year, today.month)
    return r["ey"] < today.year or (r["ey"] == today.year and today.month >= 7)


_FEM_DIPLOMAS = ("licence", "maîtrise", "maitrise", "classe", "formation", "école", "spécialisation", "certification", "attestation", "agrégation", "habilitation")


def _un(title: str) -> str:
    return "une" if title.lower().startswith(_FEM_DIPLOMAS) else "un"


def de_institution(name: str) -> str:
    """« de l'Université de Lomé (École Polytechnique de Lomé) », « du Lycée X », « de Sciences Po »."""
    parts = [x.strip() for x in re.split(r"\s+/\s+|\s+\|\s+", name) if x.strip()]
    first, rest = parts[0], parts[1:]
    low = first.lower()
    if low[:1] in "aeiouéèêh" and low.split(" ")[0] in ("université", "universite", "école", "ecole", "institut", "académie", "academie", "hôpital", "agence", "association", "ong", "office", "observatoire", "entreprise", "university", "institute", "academy", "imperial"):
        out = f"de l'{first}"
    elif low.startswith(("lycée", "collège", "centre", "groupe", "ministère", "cabinet", "laboratoire", "conseil", "bureau", "complexe", "service")):
        out = f"du {first}"
    elif low.startswith(("faculté", "fondation", "banque", "direction", "société", "chambre", "mairie", "clinique")):
        out = f"de la {first}"
    else:
        out = f"de {first}" if low[:1] not in "aeiouéèêh" else f"d'{first}"
    return out + (f" ({', '.join(rest)})" if rest else "")


# Débuts nominaux fréquents dans les CV et verbe correspondant (« Installation et configuration de… » → « installé et configuré des… »)
NOUN_TO_VERB = {
    "analyse": "analysé", "installation": "installé", "configuration": "configuré", "déploiement": "déployé", "deploiement": "déployé",
    "évaluation": "évalué", "evaluation": "évalué", "rédaction": "rédigé", "gestion": "géré", "organisation": "organisé", "création": "créé",
    "développement": "développé", "conception": "conçu", "animation": "animé", "coordination": "coordonné", "encadrement": "encadré",
    "réalisation": "réalisé", "préparation": "préparé", "accompagnement": "accompagné", "sensibilisation": "sensibilisé",
    "administration": "administré", "supervision": "supervisé", "automatisation": "automatisé", "élaboration": "élaboré", "collecte": "collecté",
    "formation": "formé", "étude": "étudié", "migration": "migré", "modélisation": "modélisé", "conduite": "conduit", "mise en place": "mis en place",
    "mise en œuvre": "mis en œuvre", "participation": "participé", "identification": "identifié", "surveillance": "surveillé",
    "maintenance": "assuré la maintenance", "suivi": "assuré le suivi", "support": "assuré le support",
}
_VERB_TAKES_OBJECT = {"assuré la maintenance", "assuré le suivi", "assuré le support"}


def bullet_to_clause(bullet: str) -> str | None:
    """Ligne de CV → proposition au passé composé sans sujet (« analysé des vulnérabilités Web avec Nmap »), ou None."""
    b = bullet.strip().rstrip(".;")
    if not b:
        return None
    weak = apply_weak_start(b)
    if weak and weak.split(" ")[0].lower().endswith(("é", "i", "u", "t", "s")):
        return writing.lower_first(weak)
    low = b.lower()
    if any(re.match(rf"{re.escape(v)}\b", low) for v in ACTION_VERBS_FR):
        return writing.lower_first(b)
    nouns = sorted(NOUN_TO_VERB, key=len, reverse=True)
    noun_re = "|".join(re.escape(n) for n in nouns)
    m = re.match(rf"^({noun_re})(?:\s+(technique|informatique|scientifique))?(?:\s+et\s+({noun_re}))?\s+(.*)$", b, re.I)
    if not m:
        return None
    v1 = NOUN_TO_VERB[m.group(1).lower()]
    v2 = NOUN_TO_VERB[m.group(3).lower()] if m.group(3) else None
    rest = m.group(4)
    if v1 in _VERB_TAKES_OBJECT:
        if v2:
            return None
        extra = f" {m.group(2).lower()}" if m.group(2) else ""
        rest_obj = rest if re.match(r"^(de|du|des|d'|d’)\b", rest) else None
        return f"{v1}{extra} {rest_obj}" if rest_obj else (f"{v1}{extra}" if not rest else None)
    if m.group(2):
        return None
    if v2 and v2 in _VERB_TAKES_OBJECT:
        return None
    obj = _object_after("X", rest)
    if obj == rest and not re.match(r"^[A-Z0-9]", rest):  # complément sans « de » : tournure non reconnue
        return None
    verbs = f"{v1} et {v2}" if v2 else v1
    return f"{verbs} {obj}"


def _role_fr(title: str) -> tuple[str, str]:
    """(« un stage en cybersécurité », « effectué ») pour un stage, sinon (« technicien systèmes », « travaillé comme »)."""
    t = title.strip()
    m = re.match(r"^stagiaire\s+(.*)$", t, re.I)
    if m:
        return f"un stage {m.group(1)}", "stage"
    if re.match(r"^stage\b", t, re.I):
        return "un " + writing.lower_first(t), "stage"
    keep = t if re.match(r"^[A-Z]{2,}", t) else writing.lower_first(t)
    return keep, "poste"


def _place_fr(loc: str) -> str:
    if not loc:
        return ""
    if re.search(r"distance|remote|télétravail", loc, re.I):
        return ", à distance"
    city = re.split(r",|\|", loc)[0].strip()
    return f", à {city}" if city else ""


def _place_en(loc: str) -> str:
    if not loc:
        return ""
    if re.search(r"distance|remote", loc, re.I):
        return " (remote)"
    city = re.split(r",|\|", loc)[0].strip()
    return f" in {city}" if city else ""


def cv_story(p: Profile, s: Scholarship, language: str, today: date) -> dict:
    """Faits du CV mis en phrases pour la lettre : formation, expériences, compétences. Vide si le CV est dans une autre langue."""
    if not p.cv_text:
        return {}
    # CV dans une autre langue que la lettre : on garde les faits (diplômes, employeurs, dates) et les
    # intitulés d'origine entre guillemets, sans traduire le détail des missions.
    cross = writing.detect_language(p.cv_text) not in (None, language)
    from .cv import build_cv_rules  # import local : cv importe déjà ce module indirectement

    built = build_cv_rules(p.cv_text, p, s, None, today=today)
    secs = {sec["key"]: sec for sec in built["sections"]}
    en = language == "en"
    out: dict[str, list[str]] = {"education": [], "experience": [], "skills": [], "mention": []}

    edus = sorted((secs.get("education") or {}).get("entries", []), key=lambda e: (parse_range(e["dates"])["ey"] or 0), reverse=True)
    for i, e in enumerate(edus[:2]):
        title = e["title"].strip()
        if not title:
            continue
        r = parse_range(e["dates"])
        org = e.get("organization", "")
        if cross:
            title = f"{diploma_noun(title, language)} ({quote(title, language)})"
        if en:
            org_en = re.sub(r" / (.*)$", r" (\1)", org)
            if re.match(r"^(university|institute|polytechnic|school|college|academy) of\b", org_en, re.I):
                org_en = "the " + org_en
            where = f" from {org_en}" if org and i == 0 else ""
            if i == 0:
                out["education"].append(f"I hold a {title}{where}" + (f", completed in {r['ey']}." if r["ey"] else ".") if _finished(r, today)
                                        else f"I am currently studying for a {title}" + (f" at {org}" if org else "") + (f", which I will complete in {r['ey']}." if r["ey"] else "."))
            else:
                out["education"].append(f"Before that, I earned a {title}" + (f" in {r['ey']}." if r["ey"] else "."))
        else:
            un = "un" if cross and not diploma_noun(e["title"], "fr").startswith("licence") else _un(title)
            fem = un == "une"
            if not cross:
                title = style.smart_lower(title)
            mention = next((re.sub(r"\s*\([^)]*\)", "", b).strip() for b in e.get("bullets", []) if b.lower().startswith("mention")), "")
            if i == 0:
                if _finished(r, today):
                    got = f", obtenu{'e' if fem else ''}" + (f" en {r['ey']}" if r["ey"] else "") + (f" avec la {writing.lower_first(mention)}" if mention else "")
                    out["education"].append(f"Je suis titulaire d'{un} {title}" + (f" {de_institution(org)}" if org else "") + (got + "." if (r["ey"] or mention) else "."))
                    if mention:
                        out["mention"] = [mention]
                else:
                    out["education"].append(f"Je prépare actuellement {un} {title}" + (f" {at_institution(org.split(' / ')[0], 'fr')}" if org else "") + (f", que j'achèverai en {r['ey']}." if r["ey"] else "."))
            else:
                out["education"].append(f"Auparavant, j'ai obtenu {un} {title}" + (f" en {r['ey']}." if r["ey"] else "."))

    exps = sorted((secs.get("experience") or {}).get("entries", []), key=lambda e: (parse_range(e["dates"])["ey"] or 9999 if parse_range(e["dates"])["ongoing"] else parse_range(e["dates"])["ey"] or 0), reverse=True)
    for e in exps[:2]:
        title = e["title"].strip()
        if not title:
            continue
        r = parse_range(e["dates"])
        org = e.get("organization", "")
        if cross:
            start, end = _when(r["sm"], r["sy"], language), _when(r["em"], r["ey"], language)
            span = _span(r, language, today)
            at = (f" at {org}" if en else f" chez {org}") if org else ""
            place = _place_en(e.get("location", "")) if en else _place_fr(e.get("location", ""))
            done = _finished(r, today)
            if en:
                verb = "I held the position of" if done else "I have held the position of"
                out["experience"].append(writing.complete_sentence(f"{span}{verb} {quote(title, 'en')}{at}{place}"))
            else:
                verb = "j'ai occupé le poste de" if done else "j'occupe le poste de"
                out["experience"].append(writing.complete_sentence(f"{span}{verb} {quote(title, 'fr')}{chez_or(org)}{place}"))
            continue
        if en:
            start, end = _when(r["sm"], r["sy"], "en"), _when(r["em"], r["ey"], "en")
            role = re.sub(r"^intern\b", "an intern", title, flags=re.I) if re.match(r"^intern\b", title, re.I) else ("an " if title[:1].lower() in "aeiou" else "a ") + title
            at = f" at {org}" if org else ""
            if _finished(r, today) and start and end and start != end:
                sent = f"{_span(r, 'en', today)}I worked as {role}{at}{_place_en(e.get('location', ''))}."
            elif not _finished(r, today) and start:
                sent = f"Since {start}, I have been working as {role}{at}{_place_en(e.get('location', ''))}."
            else:
                sent = f"I worked as {role}{at}{_place_en(e.get('location', ''))}" + (f" in {r['ey']}." if r["ey"] else ".")
            bl = next((b for b in e["bullets"] if re.match(r"^(" + "|".join(re.escape(v) for v in ACTION_VERBS_EN) + r")\b", b.lower())), None)
            if bl:
                sent += f" There, I {writing.lower_first(bl.rstrip('.;'))}."
            out["experience"].append(sent)
            continue
        role, kind = _role_fr(title)
        chez = f" {style.at_org_fr(org)}" if org else ""
        place = _place_fr(e.get("location", "")) if not re.search(r",\s*\S", org or "") else ""
        start, end = _when(r["sm"], r["sy"], "fr"), _when(r["em"], r["ey"], "fr")
        de = (lambda w: f"d'{w}" if w[:1] in "aeiouéèêh" else f"de {w}")
        if kind == "stage":
            core = f"j'ai effectué {role}{chez}{place}"
        else:
            core = f"j'ai occupé le poste {de(role)}{chez}{place}" if _finished(r, today) else f"je travaille comme {role}{chez}{place}"
        if _finished(r, today) and start and end and start != end:
            sent = f"{_span(r, 'fr', today)}{core}."
        elif not _finished(r, today) and start:
            sent = f"Depuis {start}, {core}." if kind != "stage" else f"Depuis {start}, j'effectue {role}{chez}{place}."
        else:
            sent = writing.complete_sentence(core + (f" en {r['ey']}" if r["ey"] else ""))
        clauses = []
        for b in e["bullets"][:3]:
            parts = [x.strip() for x in re.split(r"\s*;\s*", b) if x.strip()]
            conv = [bullet_to_clause(x) for x in parts]
            if conv and all(conv):
                clauses = conv
                break
        if clauses:
            body = ", puis ".join(clauses)
            body = re.sub(r"\b(ainsi que|et) (?:de |d'|d’)([a-zà-ÿ][\w-]*[sx])\b", r"\1 des \2", body)
            sent += " J'y ai " + body + "."
        out["experience"].append(sent)

    skills_sec = secs.get("skills")
    if skills_sec:
        from .cv import _skill_keywords

        keys = [re.sub(r"\s*\([^)]*\)", "", k).strip() for k in _skill_keywords(secs, 8)]
        fields = [k for k in keys if len(k.split()) > 1 and k.split()[1][:1].islower()]
        keys = [k for k in keys if k not in fields][:5]
        if cross:
            keys = [k for k in keys if re.match(r"^[A-Z0-9]", k) and writing.detect_language(k) is None and not re.search(r"\b(de|des|et|du|la|le|of|and|the)\b", k)][:5]
        if len(keys) >= 3:
            sent = ("I am proficient in " if en else "Je maîtrise notamment ") + _join_actions_raw(keys, language)
            if fields and not cross and not en:
                sent += ", et j'ai acquis des compétences en " + " et en ".join(writing.lower_first(f) for f in fields[:2])
            out["skills"].append(sent + ".")
    return out


DIPLOMA_NOUNS = [
    (r"\b(master|msc|m\.sc|ma\b|mba|mphil|maîtrise)", ("master", "master's degree")),
    (r"\b(licence|bachelor|bsc|b\.sc|ba\b|beng|undergraduate)", ("licence", "bachelor's degree")),
    (r"\b(doctorat|phd|ph\.d|doctorate)", ("doctorat", "PhD")),
    (r"\b(bts|dut|hnd|diploma|diplôme universitaire)", ("diplôme de technicien supérieur", "higher technical diploma")),
    (r"\b(baccalauréat|bac\b|high school|a-levels|waec|wassce)", ("baccalauréat", "secondary school diploma")),
    (r"\b(ingénieur|engineer)", ("diplôme d'ingénieur", "engineering degree")),
]


def diploma_noun(title: str, language: str) -> str:
    low = title.lower()
    for pat, (fr, en) in DIPLOMA_NOUNS:
        if re.search(pat, low):
            return en if language == "en" else fr
    return "degree" if language == "en" else "diplôme"


def quote(text: str, language: str) -> str:
    return f"“{text}”" if language == "en" else f"« {text} »"


def chez_or(org: str) -> str:
    return f" chez {org}" if org else ""


def _span(r: dict, language: str, today: date) -> str:
    """Début de phrase daté : « De février à mars 2026, », « D'avril 2023 à avril 2026, », « From April 2023 to April 2026, »."""
    if not r["sy"]:
        return ""
    en = language == "en"
    if not _finished(r, today):
        return f"Since {_when(r['sm'], r['sy'], 'en')}, " if en else f"Depuis {_when(r['sm'], r['sy'], 'fr')}, "
    if r["sy"] == r["ey"] and r["sm"] and r["em"] and r["sm"] != r["em"]:
        a, b = (EN_MONTHS[r["sm"] - 1], f"{EN_MONTHS[r['em'] - 1]} {r['ey']}") if en else (FR_MONTHS[r["sm"] - 1], f"{FR_MONTHS[r['em'] - 1]} {r['ey']}")
    else:
        a, b = _when(r["sm"], r["sy"], language), _when(r["em"], r["ey"], language)
    if a == b:
        return f"In {a}, " if en else f"En {a}, "
    if en:
        return f"From {a} to {b}, "
    return (f"D'{a} à {b}, " if a[:1] in "aeiouéèêh" else f"De {a} à {b}, ")


def _overlap(a: str, b: str) -> float:
    """Part des mots significatifs de ``a`` présents dans ``b``."""
    wa = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", a.lower())}
    wb = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", b.lower())}
    return len(wa & wb) / len(wa) if wa else 0.0


_ACRONYM_ARTICLE = {"DAAD": "le ", "AUF": "l'", "OIF": "l'", "USAID": "l'", "BAD": "la ", "BOAD": "la ", "JICA": "la ", "KOICA": "la ",
                    "CEDEAO": "la ", "UEMOA": "l'", "OMS": "l'", "UNESCO": "l'", "PNUD": "le ", "IRD": "l'", "CNRS": "le ", "ARES": "l'",
                    "VLIR-UOS": "le ", "DFID": "le ", "FCDO": "le ", "CSC": "le ", "TWAS": "la ", "ICTP": "l'", "AIMS": "l'"}


def par_org(org: str) -> str:
    """« par le Gouvernement du Royaume-Uni », « par la Fondation Mastercard », « par l'Agence universitaire », « par Campus France »."""
    o = (org or "").strip().split(" / ")[0].strip()
    first = o.split(" ")[0].lower() if o else ""
    acr = _ACRONYM_ARTICLE.get(o.upper()) if o.isupper() else None
    if acr:
        return f"par {acr}{o}"
    if first in ("gouvernement", "ministère", "département", "conseil", "programme", "fonds", "service", "centre", "réseau", "consortium", "bureau", "secrétariat"):
        return f"par le {o}"
    if first in ("fondation", "banque", "commission", "confédération", "région", "république", "fédération", "communauté", "coopération", "délégation"):
        return f"par la {o}"
    if first in ("agence", "université", "organisation", "ambassade", "office", "union", "académie", "institut", "école", "association"):
        return f"par l'{o}"
    return f"par {o}"


def _join_actions_raw(items: list[str], language: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + (" and " if language == "en" else " et ") + items[-1]


def _usable(text: str | None, language: str) -> bool:
    """Une réponse est reprise telle quelle seulement si elle est dans la langue de la lettre (sans IA, pas de traduction)."""
    return bool(text and text.strip()) and writing.detect_language(text) in (None, language)


_FR_ORG = re.compile(r"\b(gouvernement|minist[èe]re|ambassade|universit[ée]|fondation|agence|coop[ée]ration|bourses?|conseil|r[ée]publique|de la|du|des|et)\b", re.I)




# ------------------------------------------------------------------ modèle hors-ligne
def letter_template(p: Profile, s: Scholarship, answers: dict, language: str, max_words: int, notes: list[str] | None = None, today: date | None = None) -> list[str]:
    today = today or date.today()
    en = language == "en"
    notes = notes if notes is not None else []
    domain = (domain_name(p.domain, language) or "").lower() if p.domain and p.domain != "tous" else ""
    target = LEVEL_PHRASE["en" if en else "fr"].get(p.target_level or "", "")
    current = CURRENT_PHRASE["en" if en else "fr"].get(p.current_level or "", "")
    countries = [c for c in (s.study_countries or [])]
    country = country_name(countries[0], language) if len(countries) == 1 else ""
    where_fr = writing.country_in(countries[0], country) if country else ""
    where_en = writing.country_in_en(countries[0], country) if country else ""
    skipped: list[str] = []

    def ans(key: str) -> str:
        v = (answers.get(key) or "").strip()
        if v and not _usable(v, language):
            skipped.append(key)
            return ""
        return v

    program = ans("target_program").rstrip(".")
    fem = p.gender == "f"
    story = cv_story(p, s, language, today)
    if p.cv_text and writing.detect_language(p.cv_text) not in (None, language):
        notes.append(t(f"Votre CV n'est pas en {'anglais' if en else 'français'} : la lettre reprend vos diplômes, postes et dates avec leurs intitulés d'origine, sans le détail de vos missions. Importez votre CV dans la langue de la lettre pour une version plus complète.",
                       f"Your CV is not in {'English' if en else 'French'}: the letter uses your degrees, positions and dates with their original titles, without the detail of your tasks. Import your CV in the language of the letter for a fuller version."))
    paragraphs: list[str] = []

    # 1. Objet de la lettre
    if en:
        org = s.organization if s.organization and not _FR_ORG.search(s.organization) else ""
        if org and org.split(" / ")[0].strip().lower() in (s.title or "").lower():
            org = ""
        p1 = f"I am applying for {bourse_name_en(s)}" + (f", offered by {org}," if org else "")
        if target:
            p1 += f" to pursue {target}" + (f" in {domain}" if domain else "")
        if where_en:
            p1 += f" {where_en}"
        p1 += "."
        if program:
            p1 += f" The programme I am aiming for is {program}."
    else:
        org_main = (s.organization or "").split(" / ")[0].strip()
        if org_main and org_main.lower() in (s.title or "").lower():
            p1 = f"Je vous adresse ma candidature {a_bourse_fr(s)}"
        else:
            p1 = f"Je vous adresse ma candidature {a_bourse_fr(s)}, {offered_fr(s)} {par_org(s.organization)}"
        if target:
            p1 += f", pour préparer {target}" + (f" en {domain}" if domain else "")
        if where_fr:
            p1 += f" {where_fr}"
        p1 += "."
        if program:
            p1 += f" Je vise plus précisément le programme « {program} »."
    paragraphs.append(p1)

    # 2. Formation
    parts = list(story.get("education", []))
    if not parts and (p.institution or current):
        if en:
            parts.append(f"I am currently completing {current or 'my studies'}" + (f" in {domain}" if domain else "") + (f" {at_institution(p.institution, 'en')}" if p.institution else "") + ".")
        else:
            parts.append(f"Je poursuis actuellement {current or 'mes études'}" + (f" en {domain}" if domain else "") + (f" {at_institution(p.institution, 'fr')}" if p.institution else "") + ".")
    if p.grade_average is not None and not story.get("mention"):
        parts.append(f"My average grade is {_num(p.grade_average, 'en')} out of 20." if en else f"Ma moyenne générale est de {_num(p.grade_average, 'fr')} sur 20.")
    if parts:
        paragraphs.append(" ".join(parts))

    # 3. Expérience, tirée du CV (sans répéter la réalisation que l'étudiant raconte plus loin)
    proud_raw = ans("proud_of")
    exp_sents = []
    for sent in story.get("experience", []):
        head, sep, detail = sent.partition(" There, I " if en else " J'y ai ")
        if sep and proud_raw and _overlap(detail, proud_raw) >= 0.5:
            sent = head
        exp_sents.append(sent)
    # Réalisation marquante, racontée dans le même paragraphe que l'expérience
    proud = writing.first_person(proud_raw, "J'ai", "I", language)
    proud_sent = ""
    if proud:
        if not en and re.match(r"^j'ai\s", proud, re.I):
            proud_sent = writing.complete_sentence("Une réalisation compte particulièrement pour moi : " + writing.lower_first(proud).rstrip("."))
        elif en and re.match(r"^i\s", proud):
            proud_sent = writing.complete_sentence("One achievement matters most to me: " + proud.rstrip("."))
        else:
            lead = "One experience shaped this application more than any other." if en else "Une expérience a particulièrement orienté ce projet."
            proud_sent = f"{lead} {proud}"
    parts = exp_sents + ([proud_sent] if proud_sent else []) + list(story.get("skills", []))
    if not story:
        highlights = cv_highlights(p.cv_text, language) if not p.cv_text or writing.detect_language(p.cv_text) in (None, language) else []
        if highlights:
            parts.append(("Alongside my studies, I " if en else "En parallèle de ma formation, j'ai ") + _join_actions(highlights, language) + ".")
    if parts:
        paragraphs.append(" ".join(parts))

    # 5. Pourquoi ce pays, ce programme, plan d'études
    parts = []
    why_country = ans("why_country")
    if why_country and countries:
        from ..vocab import COUNTRIES as _C
        others = [n for c, n in _C.items() if c not in countries and len(n) > 3 and re.search(rf"\b{re.escape(n)}\b", why_country, re.I)]
        if others:
            notes.append(t(f"Votre réponse « pourquoi ce pays » parle de {others[0]}, alors que cette bourse finance des études {where_fr or 'dans un autre pays'} : elle n'a pas été reprise. Réécrivez-la pour cette destination.",
                           f"Your answer on why this country mentions {others[0]}, but this scholarship funds studies {where_en or 'in another country'}, so it was left out. Rewrite it for this destination."))
            why_country = ""
    if why_country:
        if en:
            parts.append(_integrate(why_country, f"Studying {where_en} is a deliberate choice." if where_en else "", (f"I have chosen to study {where_en}" if where_en else "I have chosen this destination"), "en"))
        else:
            parts.append(_integrate(why_country, f"Étudier {where_fr} est un choix réfléchi." if where_fr else "", (f"J'ai choisi d'étudier {where_fr}" if where_fr else "J'ai choisi cette destination"), "fr"))
    why_program = ans("why_program")
    if why_program:
        if writing.is_infinitive_start(why_program, language):
            parts.append(writing.first_person(why_program, "Ce programme me permettra de", "This programme will allow me to", language))
        else:
            parts.append(_integrate(why_program, "", "I am applying to this programme" if en else "Je me tourne vers ce programme", language))
    plan = ans("study_plan")
    if plan:
        parts.append(writing.first_person(plan, "Pendant ma formation, je souhaite", "During the programme, I plan to", language))
    project_after = ans("project_after")
    profile_project = p.project if _usable(p.project, language) else ""
    if p.project and not profile_project:
        skipped.append("project")
    if project_after and profile_project and profile_project.strip().lower()[:30] != project_after.lower()[:30]:
        parts.append(writing.first_person(profile_project, "Je souhaite", "I want to", language))
    motivation_idx = None
    if parts:
        paragraphs.append(" ".join(x for x in parts if x))
        motivation_idx = len(paragraphs) - 1

    # 6. Projet après les études
    after = project_after or profile_project or ""
    if after.strip():
        a = after.strip()
        if en:
            if re.match(r"^i\b", a, re.I):
                paragraphs.append(writing.complete_sentence("After graduating, " + a))
            elif writing.is_infinitive_start(a, "en"):
                paragraphs.append(writing.first_person(a, "", "After graduating, I plan to", "en"))
            else:
                paragraphs.append("After graduating, my goal is precise. " + writing.as_sentences(a))
        else:
            if re.match(r"^(je|j')\b", a, re.I):
                paragraphs.append(writing.complete_sentence("À l'issue de cette formation, " + writing.lower_first(a)))
            elif writing.is_infinitive_start(a, "fr"):
                paragraphs.append(writing.first_person(a, "À l'issue de cette formation, je compte", "", "fr"))
            else:
                paragraphs.append("À l'issue de cette formation, mon objectif est précis. " + writing.as_sentences(a))
        themes = detect_themes(s)
        if "retour" in themes or "communaute" in themes:
            paragraphs[-1] += " This project is directly in line with the purpose of this scholarship." if en else " Ce projet rejoint directement la vocation de cette bourse."
        # Un paragraphe de deux lignes isolé fait « formulaire » : on le joint à la motivation s'ils restent courts
        if motivation_idx is not None and motivation_idx == len(paragraphs) - 2 and len((paragraphs[-2] + " " + paragraphs[-1]).split()) <= 120:
            last = paragraphs.pop()
            paragraphs[-1] = paragraphs[-1] + " " + last

    extra = writing.as_sentences(ans("extra"))
    if extra:
        paragraphs.append(extra)

    # 7. Conclusion
    if en:
        paragraphs.append("I would welcome the opportunity to discuss my application at an interview. Thank you for your time and consideration.")
    else:
        ready = "prête" if fem else ("prêt" if p.gender == "m" else "")
        if ready:
            paragraphs.append(f"Je suis {ready} à vous présenter mon projet lors d'un entretien et vous remercie de l'attention que vous porterez à ma candidature.")
        else:
            paragraphs.append("Je me tiens à votre disposition pour vous présenter mon projet lors d'un entretien et vous remercie de l'attention que vous porterez à ma candidature.")

    if skipped:
        lang_fr = "anglais" if en else "français"
        lang_en = "English" if en else "French"
        what_fr = " et ".join(x for x in [("certaines de vos réponses" if any(k != "project" for k in skipped) else ""), ("le projet de votre profil" if "project" in skipped else "")] if x)
        what_en = " and ".join(x for x in [("some of your answers" if any(k != "project" for k in skipped) else ""), ("the project in your profile" if "project" in skipped else "")] if x)
        notes.append(t(f"La lettre est en {lang_fr}, mais {what_fr} sont rédigés dans une autre langue : ces passages n'ont pas été repris. Écrivez-les en {lang_fr} pour une lettre plus complète.",
                       f"The letter is in {lang_en}, but {what_en} are written in another language, so those parts were left out. Write them in {lang_en} for a fuller letter."))

    paragraphs = [writing.fix_paragraph(x, language) for x in paragraphs if x and x.strip()]
    return _fit_words(paragraphs, max_words)


def _fit_words(paragraphs: list[str], max_words: int) -> list[str]:
    """Raccourcit en retirant la dernière phrase des paragraphes centraux les plus longs."""
    paragraphs = [x for x in paragraphs if x]
    guard = 0
    while sum(writing.word_count(x) for x in paragraphs) > max_words and len(paragraphs) > 2 and guard < 60:
        guard += 1
        middle = range(1, len(paragraphs) - 1)
        i = max(middle, key=lambda k: writing.word_count(paragraphs[k]))
        sentences = writing.split_sentences(paragraphs[i])
        if len(sentences) <= 1:
            paragraphs.pop(i)
        else:
            paragraphs[i] = " ".join(sentences[:-1])
    return paragraphs


# ------------------------------------------------------------------ IA
LETTER_SCHEMA = {
    "type": "object",
    "properties": {"paragraphs": {"type": "array", "items": {"type": "string"}}},
    "required": ["paragraphs"],
    "additionalProperties": False,
}

LETTER_SYSTEM = """Vous rédigez la lettre de motivation d'un étudiant pour une bourse d'études. La lettre sera lue par un
jury qui en lit des centaines : elle doit être précise, personnelle et sobre, et ne jamais sonner comme un
texte produit en série.

Vous rendez uniquement le CORPS de la lettre (les paragraphes entre la formule d'appel et la formule de
politesse). L'en-tête, l'objet, la formule d'appel, la formule de politesse et la signature sont ajoutés
ensuite par la plateforme : ne les écrivez pas.

Construction (4 à 6 paragraphes) :
1. Une ouverture qui nomme la bourse et le diplôme visé, et qui donne d'emblée un fait marquant propre
   à l'étudiant (une réalisation, un déclic, un problème concret observé). Pas de phrase d'introduction vide.
2. Le parcours : formation, résultats, expériences les plus utiles à cette candidature, avec les faits du CV.
3. Le choix du pays, du programme et le plan d'études : cours, laboratoire, méthode, sujet de mémoire,
   en reprenant les réponses de l'étudiant.
4. Le projet après les études et le lien avec la mission de l'organisme qui finance la bourse.
5. Une conclusion courte : disponibilité pour un entretien et remerciement.

Règles de fond :
- Utilisez uniquement les faits fournis (profil, CV, réponses). N'inventez aucune expérience, note, prix,
  chiffre, nom de cours, de laboratoire ou de professeur.
- Une information manquante ne laisse aucune trace : pas de crochets, pas d'emplacement à compléter,
  pas de phrase vague pour la remplacer. Construisez la lettre avec ce qui est disponible.
- Chaque paragraphe contient au moins un élément propre à l'étudiant ou à la bourse.

Règles de forme :
- Phrases complètes, qui se terminent toutes par un point. Pas de liste, pas de titre, pas de deux-points
  dans le corps de la lettre, pas de tiret cadratin ni demi-cadratin, pas de point de suspension.
- Proscrivez ces formules : « passionné », « depuis mon plus jeune âge », « dans un monde en constante
  évolution », « véritable tremplin », « je suis convaincu », « relever les défis », « riche et varié »,
  « fort de », « c'est avec un grand intérêt », « n'est pas seulement… mais », « plus qu'un simple »,
  « pierre angulaire », « valeur ajoutée ». En anglais : « passionate », « journey », « delve », « foster »,
  « leverage », « testament », « unwavering », « cutting-edge », « vibrant », « furthermore », « moreover »,
  « I am writing to express ».
- Variez la longueur des phrases. Verbes concrets, peu d'adjectifs. Pas de série de trois adjectifs.
- Français : registre soutenu sans lourdeur, vouvoiement du jury. Respectez le genre indiqué pour les
  accords ; si le genre n'est pas indiqué, tournez les phrases pour éviter tout accord genré et n'écrivez
  jamais « (e) ».
- Anglais : anglais britannique pour une candidature hors États-Unis et Canada, américain sinon.
- Respectez la limite de mots demandée pour le corps de la lettre.
- Écrivez comme un candidat sérieux qui aurait été relu par un conseiller expérimenté : une voix
  personnelle, des faits précis, des transitions naturelles. Le lecteur ne doit à aucun moment sentir un
  texte généré : pas de symétrie mécanique entre paragraphes, pas de conclusion qui résume tout, pas de
  phrase qui pourrait figurer dans la lettre de n'importe qui.
- Orthographe, accords, élisions (« le poste d'assistant », « à l'Université ») et prépositions devant
  les établissements (« à la Mairie de… », « au Ministère de… », « chez Orange ») doivent être parfaits."""

LETTER_REVIEW_SYSTEM = """Vous êtes conseiller en candidatures de bourses et correcteur professionnel. Vous relisez le corps
d'une lettre de motivation avant son envoi au jury.

Corrigez sans rien inventer : orthographe, grammaire, accords, élisions, prépositions, ponctuation,
répétitions, tournures maladroites ou trop scolaires, phrases qui sonnent comme un texte généré
(formules creuses, symétries, énumérations de trois adjectifs, conclusions qui résument). Gardez les faits,
l'ordre des idées, la langue, le nombre de paragraphes à un près et la longueur à 10 % près.
Ne mettez ni titre, ni liste, ni deux-points, ni tiret cadratin. Rendez la lettre corrigée."""


STATEMENT_LABEL = {
    "lettre": "lettre de motivation",
    "essais": "plusieurs essais courts (par exemple leadership, réseau, choix du pays, projet de carrière) : rédigez une lettre dont chaque paragraphe peut servir de base à un essai",
    "personal_statement": "personal statement : récit personnel et argumenté, sans formules de lettre",
    "projet_recherche": "lettre accompagnée d'un projet de recherche : insistez sur le sujet, la méthode et le laboratoire visé",
}

STATEMENT_NOTE = {
    "essais": ("Cette bourse demande plusieurs essais courts plutôt qu'une lettre. Servez-vous de chaque paragraphe comme base pour un essai et respectez les limites de mots du formulaire officiel.",
               "This scholarship asks for several short essays rather than a letter. Use each paragraph as the basis for one essay and respect the word limits of the official form."),
    "personal_statement": ("Cette bourse demande un personal statement : reprenez le corps de cette lettre sans l'en-tête ni les formules de politesse.",
                           "This scholarship asks for a personal statement: reuse the body of this letter without the header and closing formulas."),
    "projet_recherche": ("Cette bourse demande aussi un projet de recherche (sujet, méthode, calendrier, laboratoire d'accueil). Préparez-le à part, la lettre y fait référence.",
                         "This scholarship also asks for a research proposal (topic, method, timeline, host lab). Prepare it separately; the letter refers to it."),
}


def _ai_user_prompt(p: Profile, s: Scholarship, answers: dict, language: str, max_words: int, tone: str) -> str:
    gender = {"f": "féminin", "m": "masculin"}.get(p.gender or "", "non indiqué")
    countries = ", ".join(country_name(c, "fr") for c in (s.study_countries or [])) or "plusieurs pays"
    themes = ", ".join(THEMES[k]["label"] for k in detect_themes(s)) or "non précisés"
    ans = "\n".join(f"{label} : {answers.get(key) or '-'}" for key, label in QUESTIONS)
    return f"""Langue : {'anglais' if language == 'en' else 'français'} ({'américain' if letter_style(s, language) == 'en_us' else 'britannique' if language == 'en' else 'France'}).
Limite du corps de la lettre : {max_words} mots environ ; visez entre {int(max_words * 0.8)} et {max_words} mots si les faits fournis le permettent, sans remplissage. Ton : {tone}. Genre grammatical du candidat : {gender}.
Date du jour : {date.today().isoformat()}. Déduisez des dates du CV si chaque diplôme est obtenu ou en cours et si chaque poste est terminé ou actuel, et conjuguez en conséquence.
Le CV et les réponses peuvent être rédigés dans une autre langue que la lettre : traduisez fidèlement les faits dans la langue de la lettre. Les intitulés officiels de diplômes peuvent garder leur nom d'origine.

BOURSE
Nom officiel : {s.title}
Nom à employer dans la lettre : {short_title(s, language)}
Organisme : {s.organization}
Pays d'études : {countries}
Description : {s.summary}
Conditions : {'; '.join(s.eligibility or []) or '-'}
Ce que le jury valorise : {themes}
Document de motivation demandé : {STATEMENT_LABEL.get(getattr(s, 'statement_type', None) or 'lettre', 'lettre de motivation')}

PROFIL
Nom : {p.full_name}
Niveau actuel : {LEVEL_PHRASE['fr'].get(p.current_level or '', '-')} ; diplôme visé : {LEVEL_PHRASE['fr'].get(p.target_level or '', '-')}
Domaine : {DOMAINS.get(p.domain or '', '-')}
Établissement : {p.institution or '-'} ; moyenne : {p.grade_average if p.grade_average is not None else '-'} sur 20
Expériences : {p.experiences or '-'}
Engagement : {p.engagement or '-'}
Projet : {p.project or '-'}
Années d'expérience professionnelle : {p.work_experience_years if getattr(p, 'work_experience_years', None) is not None else '-'}
Centres d'intérêt : {getattr(p, 'interests', None) or '-'}
Langues : {p.languages} ; tests : {p.language_scores}

RÉPONSES DU CANDIDAT
{ans}

CV
{(p.cv_text or '-')[:9000]}"""


def check_letter(paragraphs: list[str], language: str, max_words: int) -> list[str]:
    """Problèmes de forme qui justifient une réécriture."""
    issues = []
    body = "\n".join(paragraphs)
    for c in writing.find_cliches(body, language):
        issues.append(f"formule à retirer : « {c} »")
    if re.search(r"\S\s?:\s", body):
        issues.append("deux-points dans le corps de la lettre")
    if "[" in body or "]" in body:
        issues.append("emplacement entre crochets")
    for x in paragraphs:
        if x.strip() and x.strip()[-1] not in ".!?»":
            issues.append(f"phrase incomplète : « {x.strip()[-60:]} »")
    if language == "fr" and re.search(r"\(e\)|\(es\)", body):
        issues.append("écriture « (e) »")
    words = writing.word_count(body)
    if words > max_words:
        issues.append(f"trop long ({words} mots pour {max_words})")
    if len(paragraphs) < 3:
        issues.append("pas assez de paragraphes")
    return issues


def _ai_paragraphs(system_user: str, language: str, max_words: int) -> list[str] | None:
    data = ask_json(LETTER_SYSTEM, system_user, LETTER_SCHEMA, effort="high", max_tokens=8000)
    if not data or not data.get("paragraphs"):
        return None
    paragraphs = [x.strip() for x in data["paragraphs"] if x.strip()]
    issues = check_letter(paragraphs, language, max_words)
    if issues:
        retry = system_user + "\n\nVERSION PRÉCÉDENTE\n" + "\n\n".join(paragraphs) + "\n\nCORRIGEZ CES POINTS\n- " + "\n- ".join(issues)
        data2 = ask_json(LETTER_SYSTEM, retry, LETTER_SCHEMA, effort="high", max_tokens=8000)
        if data2 and data2.get("paragraphs"):
            paragraphs = [x.strip() for x in data2["paragraphs"] if x.strip()]
    # Seconde lecture « expert » : orthographe, fluidité, rien qui sonne généré
    review = ask_json(LETTER_REVIEW_SYSTEM, f"Langue : {'anglais' if language == 'en' else 'français'}. Limite : {max_words} mots.\n\nLETTRE\n" + "\n\n".join(paragraphs),
                      LETTER_SCHEMA, effort="high", max_tokens=8000)
    if review and review.get("paragraphs"):
        reviewed = [x.strip() for x in review["paragraphs"] if x.strip()]
        if reviewed and abs(len(reviewed) - len(paragraphs)) <= 1 and not check_letter(reviewed, language, max_words):
            paragraphs = reviewed
    return paragraphs


# ------------------------------------------------------------------ point d'entrée
def readiness(p: Profile, email: str | None) -> list[dict]:
    """Informations indispensables pour une lettre et un CV propres."""
    missing = []
    if not p.full_name:
        missing.append({"field": "full_name", "label": "Nom complet"})
    if not p.phone:
        missing.append({"field": "phone", "label": "Téléphone"})
    if not p.city:
        missing.append({"field": "city", "label": "Ville de résidence"})
    if not p.residence_country:
        missing.append({"field": "residence_country", "label": "Pays de résidence"})
    if not email:
        missing.append({"field": "email", "label": "E-mail"})
    if not p.domain:
        missing.append({"field": "domain", "label": "Domaine d'études"})
    if not p.target_level:
        missing.append({"field": "target_level", "label": "Diplôme visé"})
    if not p.cv_text:
        missing.append({"field": "cv", "label": "CV importé"})
    if is_en():
        for m in missing:
            m["label"] = READINESS_EN.get(m["field"], m["label"])
    return missing


def generate_letter(p: Profile, s: Scholarship, answers: dict, language: str, max_words: int, tone: str, use_ai: bool, email: str | None = None) -> dict:
    header = build_header(p, s, email, language, answers)
    paragraphs = None
    notes: list[str] = []
    if use_ai:
        paragraphs = _ai_paragraphs(_ai_user_prompt(p, s, answers, language, max_words, tone), language, max_words)
    ai_used = paragraphs is not None
    if paragraphs is None:
        paragraphs = letter_template(p, s, answers, language, max_words, notes)
    paragraphs = [writing.fix_paragraph(x, language) for x in paragraphs]
    paragraphs = _fit_words([x for x in paragraphs if x], max_words)
    st = getattr(s, "statement_type", None)
    if st in STATEMENT_NOTE:
        notes.append(t(*STATEMENT_NOTE[st]))
    letter = {**header, "paragraphs": paragraphs, "scholarship_id": s.id, "scholarship_title": s.title, "ai_used": ai_used, "notes": notes}
    return letter


def letter_plain_text(letter: dict) -> str:
    parts = ["\n".join(letter.get("sender", [])), "\n".join(letter.get("recipient", [])), letter.get("place_date", ""),
             letter.get("subject", ""), letter.get("salutation", ""), *letter.get("paragraphs", []),
             letter.get("closing", "") if letter.get("style") != "fr" else letter.get("closing", ""), letter.get("signature", "")]
    return "\n\n".join(x for x in parts if x)


def letter_word_count(letter: dict) -> int:
    return sum(writing.word_count(x) for x in letter.get("paragraphs", []))
