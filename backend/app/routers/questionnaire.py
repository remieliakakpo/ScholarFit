"""Questionnaire de profil en 5 étapes et offres d'accompagnement.

Le site affiche les étapes telles que l'API les décrit (GET /api/questionnaire), puis envoie
toutes les réponses (POST). Sans compte : nombre de bourses trouvées et 3 aperçus sans score.
Avec un compte : le profil est enregistré, toutes les bourses avec score, et l'offre conseillée.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import i18n, offers
from ..db import get_db
from ..geo import REGIONS, region_of
from ..i18n import t
from ..matching import SITUATION_LABELS, Criteria, age_on, missing_minimum, rank, situation_labels
from ..models import Profile, Scholarship, User
from ..schemas import MatchOut
from ..security import optional_user
from ..serializers import match_out
from ..vocab import COUNTRIES, DOMAINS, LEVEL_ORDER, LEVELS

router = APIRouter(prefix="/api", tags=["questionnaire et offres"])


def _opts(d: dict[str, str]) -> list[dict]:
    return [{"value": k, "label": v} for k, v in d.items()]


CURRENT_LEVELS = {
    "lycee": "Au lycée (avant le bac)", "BAC": "Bac obtenu", "BAC3": "Licence / bachelor obtenu(e) ou en cours",
    "BAC5": "Master obtenu ou en cours", "BAC7": "Doctorat en cours ou obtenu",
}
LANGUAGE_LEVELS = {"debutant": "Débutant", "intermediaire": "Intermédiaire (B1-B2)", "courant": "Courant (C1-C2)", "natif": "Langue maternelle"}
LANGS = {"fr": "Français", "en": "Anglais", "de": "Allemand", "es": "Espagnol", "pt": "Portugais", "ar": "Arabe",
         "zh": "Chinois", "ja": "Japonais", "ko": "Coréen", "ru": "Russe", "it": "Italien", "tr": "Turc"}
CURRENT_LEVELS_EN = {
    "lycee": "In secondary school (before the baccalaureate)", "BAC": "High school diploma obtained",
    "BAC3": "Bachelor's degree obtained or in progress", "BAC5": "Master's degree obtained or in progress",
    "BAC7": "PhD in progress or obtained",
}
LANGUAGE_LEVELS_EN = {"debutant": "Beginner", "intermediaire": "Intermediate (B1-B2)", "courant": "Fluent (C1-C2)", "natif": "Native language"}
LANGS_EN = {"fr": "French", "en": "English", "de": "German", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic",
            "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ru": "Russian", "it": "Italian", "tr": "Turkish"}
TESTS = ["IELTS", "TOEFL", "DELF", "DALF", "TCF", "TEF", "TestDaF", "HSK", "JLPT", "TOPIK", "Duolingo"]


def steps() -> list[dict]:
    names = i18n.countries(COUNTRIES)
    countries = sorted(names.items(), key=lambda kv: kv[1])
    country_opts = [{"value": c, "label": n} for c, n in countries]
    # Pays d'études : chaque pays porte son continent, pour que le site réduise la liste aux continents choisis
    dest_opts = [{"value": c, "label": n, "region": region_of(c)} for c, n in countries]
    domains = i18n.loc(DOMAINS, i18n.DOMAINS_EN)
    return [
        {
            "id": "identite", "title": t("Vous", "About you"),
            "subtitle": t("Votre nationalité détermine la plupart des bourses ouvertes.",
                          "Your nationality determines most of the scholarships open to you."),
            "questions": [
                {"id": "nationalities", "label": t("Votre ou vos nationalités", "Your nationality or nationalities"), "type": "countries",
                 "required": True, "options": country_opts},
                {"id": "residence_country", "label": t("Pays où vous vivez aujourd'hui", "Country where you live today"), "type": "country",
                 "required": False, "options": country_opts},
                {"id": "birth_date", "label": t("Date de naissance", "Date of birth"), "type": "date", "required": True,
                 "placeholder": t("Beaucoup de bourses fixent un âge maximum", "Many scholarships set a maximum age")},
            ],
        },
        {
            "id": "etudes", "title": t("Vos études", "Your studies"),
            "subtitle": t("Où vous en êtes et ce que vous souhaitez financer.", "Where you are now and what you would like to fund."),
            "questions": [
                {"id": "current_level", "label": t("Votre niveau actuel", "Your current level"), "type": "select", "required": True,
                 "options": _opts(i18n.loc(CURRENT_LEVELS, CURRENT_LEVELS_EN))},
                {"id": "target_level", "label": t("Le diplôme que vous souhaitez financer", "The degree you would like to fund"), "type": "select",
                 "required": True, "options": _opts(i18n.loc(LEVELS, i18n.LEVELS_EN))},
                {"id": "domain", "label": t("Votre domaine", "Your field of study"), "type": "select", "required": True,
                 "options": _opts({k: v for k, v in domains.items() if k != "tous"})},
                {"id": "grade_average", "label": t("Votre moyenne sur 20 (dernière année)", "Your average out of 20 (last year)"),
                 "type": "number", "required": False, "placeholder": t("ex. 14,5", "e.g. 14.5")},
            ],
        },
        {
            "id": "destination", "title": t("Votre destination", "Your destination"),
            "subtitle": t("Laissez vide pour chercher partout dans le monde.", "Leave empty to search worldwide."),
            "questions": [
                {"id": "wished_regions", "label": t("Régions qui vous intéressent", "Regions you are interested in"), "type": "multiselect",
                 "required": False, "options": _opts(i18n.loc(REGIONS, i18n.REGIONS_EN))},
                {"id": "wished_countries", "label": t("Pays précis (facultatif)", "Specific countries (optional)"), "type": "countries",
                 "required": False, "options": dest_opts, "filter_by": "wished_regions"},
                {"id": "full_funding_only", "label": t("Seulement les bourses complètes (frais, logement, voyage)",
                                                       "Fully funded scholarships only (fees, accommodation, travel)"),
                 "type": "boolean", "required": False},
            ],
        },
        {
            "id": "langues", "title": t("Vos langues", "Your languages"),
            "subtitle": t("Un score de test ouvre beaucoup de portes.", "A test score opens many doors."),
            "questions": [
                {"id": "languages", "label": t("Langues que vous parlez", "Languages you speak"), "type": "multiselect", "required": True,
                 "options": _opts(i18n.loc(LANGS, LANGS_EN))},
                {"id": "language_scores", "label": t("Tests de langue passés (score)", "Language tests taken (score)"), "type": "language_scores",
                 "required": False, "options": [{"value": x, "label": x} for x in TESTS],
                 "placeholder": t("ex. IELTS 6,5", "e.g. IELTS 6.5")},
            ],
        },
        {
            "id": "situation", "title": t("Votre situation et votre besoin d'aide", "Your situation and the support you need"),
            "subtitle": t("Pour vous montrer les bourses réservées et l'offre qui vous convient.",
                          "To show you reserved scholarships and the option that suits you."),
            "questions": [
                {"id": "situations", "label": t("Ces situations vous concernent-elles ? (facultatif, reste privé)",
                                                "Do any of these apply to you? (optional, kept private)"), "type": "multiselect",
                 "required": False, "options": _opts(situation_labels())},
                {"id": "applications_planned", "label": t("À combien de bourses souhaitez-vous postuler ?",
                                                          "How many scholarships would you like to apply for?"),
                 "type": "number", "required": False, "placeholder": t("ex. 3", "e.g. 3")},
                {"id": "help_preference", "label": t("Comment souhaitez-vous postuler ?", "How would you like to apply?"), "type": "select",
                 "required": True, "options": _opts(offers.help_preferences())},
                {"id": "project", "label": t("Votre projet en une ou deux phrases", "Your plan in one or two sentences"), "type": "text",
                 "required": False, "placeholder": t("ex. Devenir ingénieure en énergies renouvelables au Sénégal",
                                                     "e.g. Become a renewable energy engineer in Senegal")},
            ],
        },
    ]


class QuestionnaireIn(BaseModel):
    answers: dict


class QuestionnaireOut(BaseModel):
    total_matches: int
    # Bourses situées dans les pays ou continents choisis (affichées en premier), le reste suit
    # sous « Autres bourses disponibles ». has_destination = faux si rien n'a été choisi.
    destination_total: int = 0
    has_destination: bool = False
    excluded_count: int
    items: list[MatchOut]
    recommended_offer: str
    offers: list[dict]
    profile_saved: bool
    missing: list[str]


def _clean(a: dict) -> dict:
    """Valide et normalise les réponses (codes connus seulement)."""
    out: dict = {}
    nats = [c for c in a.get("nationalities") or [] if c in COUNTRIES]
    if nats:
        out["nationalities"] = nats
    if a.get("residence_country") in COUNTRIES:
        out["residence_country"] = a["residence_country"]
    if a.get("birth_date"):
        try:
            bd = date.fromisoformat(str(a["birth_date"])[:10])
        except ValueError:
            raise HTTPException(422, t("Date de naissance invalide (format AAAA-MM-JJ)", "Invalid date of birth (format YYYY-MM-DD)"))
        if bd > date.today():
            raise HTTPException(422, t("Date de naissance dans le futur", "Date of birth is in the future"))
        out["birth_date"] = bd
    cur = a.get("current_level")
    if cur in LEVELS:
        out["current_level"] = cur
    if a.get("target_level") in LEVELS:
        out["target_level"] = a["target_level"]
    elif cur in CURRENT_LEVELS:  # déduit : le diplôme suivant
        nxt = {"lycee": "BAC", "BAC": "BAC3", "BAC3": "BAC5", "BAC5": "BAC7", "BAC7": "BAC7"}[cur]
        out["target_level"] = nxt if nxt in LEVEL_ORDER else None
    if a.get("domain") in DOMAINS:
        out["domain"] = a["domain"]
    if a.get("grade_average") not in (None, ""):
        try:
            g = float(str(a["grade_average"]).replace(",", "."))
        except ValueError:
            raise HTTPException(422, t("Moyenne invalide", "Invalid average"))
        if not 0 <= g <= 20:
            raise HTTPException(422, t("La moyenne doit être entre 0 et 20", "The average must be between 0 and 20"))
        out["grade_average"] = g
    out["wished_regions"] = [r for r in a.get("wished_regions") or [] if r in REGIONS]
    out["wished_countries"] = [c for c in a.get("wished_countries") or [] if c in COUNTRIES]
    out["full_funding_only"] = bool(a.get("full_funding_only"))
    langs = a.get("languages") or []
    if isinstance(langs, dict):
        out["languages"] = {k: str(v) for k, v in langs.items() if k in LANGS}
    else:
        out["languages"] = {k: "courant" for k in langs if k in LANGS}
    scores = {}
    for k, v in (a.get("language_scores") or {}).items():
        try:
            if k in TESTS and v not in (None, ""):
                scores[k] = float(str(v).replace(",", "."))
        except ValueError:
            raise HTTPException(422, t(f"Score invalide pour {k}", f"Invalid score for {k}"))
    out["language_scores"] = scores
    out["situations"] = [x for x in a.get("situations") or [] if x in SITUATION_LABELS]
    if a.get("applications_planned") not in (None, ""):
        try:
            out["applications_planned"] = max(1, min(50, int(a["applications_planned"])))
        except (TypeError, ValueError):
            raise HTTPException(422, t("Nombre de bourses invalide", "Invalid number of scholarships"))
    if a.get("help_preference") in offers.HELP_PREFERENCES:
        out["help_preference"] = a["help_preference"]
    if a.get("project"):
        out["project"] = str(a["project"])[:2000]
    return out


@router.get("/questionnaire")
def questionnaire():
    return {"steps": steps()}


@router.post("/questionnaire", response_model=QuestionnaireOut)
def submit(body: QuestionnaireIn, kind: str = Query("bourse", pattern="^(bourse|stage|conference|tout)$"), user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    data = _clean(body.answers)
    today = date.today()
    if user is not None:
        p = user.profile or Profile()
        user.profile = p
        for k, v in data.items():
            setattr(p, k, v)
        p.questionnaire_done_at = datetime.now(timezone.utc)
        db.commit()
        c = Criteria.from_profile(p, today)
    else:
        p = Profile(**{k: v for k, v in data.items()})
        c = Criteria(
            target_level=data.get("target_level"), nationalities=data.get("nationalities", []),
            age=age_on(data["birth_date"], today) if data.get("birth_date") else None, domain=data.get("domain"),
            wished_countries=data["wished_countries"], wished_regions=data["wished_regions"],
            grade_average=data.get("grade_average"), language_scores=data["language_scores"],
            languages=list(data["languages"]), project_text=data.get("project", ""),
            full_funding_only=data["full_funding_only"], situations=data["situations"],
        )
    stmt = select(Scholarship) if kind == "tout" else select(Scholarship).where(Scholarship.kind == kind)
    results, excluded = rank(list(db.scalars(stmt)), c, today, limit=500)
    dest = c.strict_destination()
    items = [match_out(m) for m in results]
    if dest:
        for m in items:
            m.in_destination = bool(set(m.scholarship.study_countries or []) & dest)
        items.sort(key=lambda m: not m.in_destination)  # tri stable : l'ordre du score est gardé
    destination_total = sum(1 for m in items if m.in_destination)
    if user is None:  # aperçu : 3 bourses, sans score (réservé aux comptes)
        items = items[:3]
        for m in items:
            m.score, m.chance = None, None
    rec = offers.recommend(p)
    return QuestionnaireOut(
        total_matches=len(results), destination_total=destination_total, has_destination=bool(dest), excluded_count=excluded, items=items, recommended_offer=rec,
        offers=[{**o, "recommended": o["code"] == rec} for o in offers.catalog()],
        profile_saved=user is not None, missing=missing_minimum(c),
    )


@router.get("/offres")
def list_offers(user: User | None = Depends(optional_user)):
    """Les trois façons de postuler : seul (gratuit), Standard, Premium. Avec un jeton,
    ``recommended`` suit le profil de la personne connectée."""
    return offers.with_recommendation(user.profile if user else None)
