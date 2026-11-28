"""Langue des textes servis par l'API : français par défaut, anglais avec ?lang=en (ou le cookie sf_lang=en).

La langue est lue une fois par requête (middleware ASGI ``LangMiddleware``) et rangée dans une
variable de contexte : les fonctions qui fabriquent les textes (dates limites, conditions, matching…)
appellent ``t("texte français", "English text")`` sans qu'on ait à passer la langue partout.
"""
from __future__ import annotations

from contextvars import ContextVar
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

import pycountry

LANGS = ("fr", "en")
_lang: ContextVar[str] = ContextVar("lang", default="fr")
_explicit: ContextVar[bool] = ContextVar("lang_explicit", default=False)


def lang() -> str:
    return _lang.get()


def set_lang(value: str | None):
    return _lang.set(value if value in LANGS else "fr")


def explicit() -> bool:
    """La requête a choisi sa langue (paramètre ou cookie) : on peut la retenir pour le compte."""
    return _explicit.get()


def is_en() -> bool:
    return _lang.get() == "en"


def t(fr: str, en: str) -> str:
    return en if is_en() else fr


def loc(fr: dict, en: dict) -> dict:
    """Le dictionnaire de libellés dans la langue courante (les clés absentes de ``en`` restent en français)."""
    return {k: en.get(k, v) for k, v in fr.items()} if is_en() else fr


class LangMiddleware:
    """Lit ``lang`` dans l'adresse, sinon le cookie ``sf_lang``."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        value = (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("lang") or [None])[0]
        if value is None:
            raw = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"cookie"), "")
            jar = SimpleCookie()
            try:
                jar.load(raw)
            except Exception:  # noqa: BLE001 - cookie mal formé : français
                pass
            value = jar["sf_lang"].value if "sf_lang" in jar else None
        token = set_lang((value or "fr").lower()[:2])
        flag = _explicit.set(value is not None)
        try:
            await self.app(scope, receive, send)
        finally:
            _lang.reset(token)
            _explicit.reset(flag)


# ------------------------------------------------------------------ listes en anglais
LEVELS_EN = {
    "BAC": "High school diploma (foundation year)",
    "BAC3": "Bachelor's degree",
    "BAC5": "Master's degree",
    "BAC7": "PhD and postdoc",
}
KINDS_EN = {"bourse": "Scholarship", "stage": "Internship", "conference": "Conference", "formation": "Training",
            "concours": "Competition", "echange": "Exchange programme", "fellowship": "Fellowship", "cours_en_ligne": "Online course"}
DOMAINS_EN = {
    "agriculture": "Agriculture and agronomy",
    "arts": "Arts, design and architecture",
    "biologie": "Biology and life sciences",
    "chimie": "Chemistry",
    "droit": "Law and political science",
    "economie": "Economics and management",
    "education": "Education",
    "energie": "Energy and environment",
    "informatique": "Computer science and digital",
    "ingenierie": "Engineering",
    "langues": "Languages, literature and humanities",
    "mathematiques": "Mathematics and statistics",
    "medecine": "Medicine and health",
    "physique": "Physics",
    "relations_internationales": "International relations and development",
    "sciences_sociales": "Social sciences and psychology",
    "journalisme": "Journalism and communication",
    "tous": "All fields",
}
REGIONS_EN = {"afrique": "Africa", "europe": "Europe", "amerique": "Americas", "asie": "Asia and Middle East", "oceanie": "Oceania"}
DEADLINE_STATUSES_EN = {"urgente": "Urgent (14 days or less)", "bientot": "Soon (45 days or less)",
                        "ouverte": "Open", "inconnue": "Date not published", "expiree": "Closed"}
APPLICATION_STATUSES_EN = {"a_preparer": "To prepare", "en_cours": "In progress", "envoyee": "Submitted",
                           "acceptee": "Accepted", "refusee": "Rejected"}
COVERAGE_EN = {"frais": "tuition fees", "logement": "accommodation", "voyage": "flights",
               "allocation": "monthly stipend", "assurance": "health insurance"}

_COUNTRY_OVERRIDES = {
    "XK": "Kosovo", "KR": "South Korea", "KP": "North Korea", "RU": "Russia", "IR": "Iran", "SY": "Syria",
    "LA": "Laos", "VN": "Vietnam", "TZ": "Tanzania", "CD": "DR Congo", "CG": "Republic of the Congo",
    "BO": "Bolivia", "VE": "Venezuela", "MD": "Moldova", "PS": "Palestine", "FM": "Micronesia",
    "TW": "Taiwan", "BN": "Brunei", "CV": "Cape Verde", "CZ": "Czech Republic", "TR": "Türkiye",
    "SZ": "Eswatini", "MK": "North Macedonia", "VA": "Vatican City", "GB": "United Kingdom", "US": "United States",
    "CI": "Côte d'Ivoire", "TL": "Timor-Leste",
}


def country_name_en(code: str, fallback: str = "") -> str:
    if code in _COUNTRY_OVERRIDES:
        return _COUNTRY_OVERRIDES[code]
    c = pycountry.countries.get(alpha_2=code)
    if not c:
        return fallback or code
    return getattr(c, "common_name", None) or c.name


_COUNTRIES_EN: dict[str, str] | None = None


def countries(fr: dict[str, str]) -> dict[str, str]:
    global _COUNTRIES_EN
    if not is_en():
        return fr
    if _COUNTRIES_EN is None:
        _COUNTRIES_EN = {code: country_name_en(code, name) for code, name in fr.items()}
    return _COUNTRIES_EN
