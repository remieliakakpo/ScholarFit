"""Choix automatique du format de CV et de lettre selon la bourse et le pays d'études.

L'étudiant ne choisit pas de modèle : la plateforme applique les usages du pays visé
(Lebenslauf en Allemagne, résumé d'une page aux États-Unis, Europass pour les programmes
européens…). Sans indication claire, on retient un CV « ATS » : une colonne, des titres
standard, aucune image ni tableau, lisible par les logiciels de tri des candidatures.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..i18n import is_en, t
from ..models import Profile, Scholarship
from ..vocab import COUNTRIES, EU

FRENCH_SPEAKING = {
    "FR", "BE", "LU", "MC", "CH", "SN", "CI", "CM", "BF", "ML", "NE", "TG", "BJ", "GA", "CG", "CD", "GN", "TD",
    "CF", "MG", "DJ", "KM", "BI", "RW", "MA", "TN", "DZ", "MR", "HT",
}
GERMAN_SPEAKING = {"DE", "AT"}
NORTH_AMERICA = {"US", "CA"}
UK_STYLE = {"GB", "IE", "AU", "NZ", "ZA", "GH", "NG", "KE", "IN", "SG", "MY", "HK"}
ASIA_DETAILED = {"CN", "JP", "KR", "TW"}


# Ordre du modèle ATS retenu par ScholarFit (CV de référence fourni le 2026-11-22) : après le
# profil, les compétences par catégorie, puis expériences, projets, formation et langues.
ATS_ORDER = ("skills", "experience", "projects", "education", "engagement", "languages", "interests")


@dataclass(frozen=True)
class CVFormat:
    code: str
    label: str
    label_en: str
    max_pages: int
    # informations personnelles admises par l'usage du pays
    show_birth_date: bool = False
    show_nationality: bool = False
    layout: str = "single"  # single | dated (dates en colonne de gauche)
    signature: bool = False  # lieu, date et nom en bas (Lebenslauf)
    summary_title_fr: str = "Profil"
    summary_title_en: str = "Profile"
    order: tuple[str, ...] = ("education", "experience", "projects", "skills", "languages", "engagement", "interests")
    rules: tuple[str, ...] = field(default_factory=tuple)


FORMATS: dict[str, CVFormat] = {
    "ats": CVFormat(
        "ats", "CV international (ATS)", "International CV (ATS-friendly)", 2,
        show_nationality=True,
        order=ATS_ORDER,
        rules=(
            "Une seule colonne, des titres de section standard, sans tableau, sans image ni pictogramme.",
            "Structure ATS : nom, titre, coordonnées, objectif de candidature, profil, compétences par catégorie, expériences, projets, formation, langues.",
            "Dates au même format partout, du plus récent au plus ancien.",
            "Mots-clés de la bourse et du domaine repris tels quels dans les expériences et compétences.",
        ),
    ),
    "francais": CVFormat(
        "francais", "CV français", "French CV", 1,
        show_nationality=True,
        order=ATS_ORDER,
        rules=(
            "Une page pour un parcours étudiant, deux au maximum en doctorat.",
            "Profil personnalisé, compétences par catégorie, expériences, projets, formation puis langues.",
            "Un titre de CV qui annonce le diplôme visé.",
        ),
    ),
    "europass": CVFormat(
        "europass", "CV Europass", "Europass CV", 2,
        show_birth_date=True, show_nationality=True, layout="dated",
        summary_title_fr="À propos de moi", summary_title_en="About me",
        order=("experience", "education", "languages", "skills", "projects", "engagement", "interests"),
        rules=(
            "Structure Europass : expérience professionnelle, éducation et formation, compétences linguistiques, compétences numériques.",
            "Langues évaluées selon le Cadre européen commun de référence (A1 à C2).",
            "Dates en colonne de gauche, du plus récent au plus ancien.",
        ),
    ),
    "lebenslauf": CVFormat(
        "lebenslauf", "Lebenslauf (usage allemand)", "Lebenslauf (German CV)", 2,
        show_birth_date=True, show_nationality=True, layout="dated", signature=True,
        summary_title_fr="Profil", summary_title_en="Profile",
        order=("education", "experience", "projects", "skills", "languages", "engagement", "interests"),
        rules=(
            "Présentation tabulaire et chronologique, mois et année pour chaque étape, sans période inexpliquée.",
            "Date de naissance et nationalité dans les informations personnelles.",
            "Lieu, date et nom en bas du document.",
        ),
    ),
    "us_resume": CVFormat(
        "us_resume", "Résumé nord-américain", "US/Canadian résumé", 1,
        summary_title_fr="Résumé", summary_title_en="Summary",
        order=ATS_ORDER[:-1],
        rules=(
            "Une page, sans photo, sans date de naissance ni nationalité (usage anti-discrimination).",
            "Chaque ligne commence par un verbe d'action et donne un résultat mesurable quand il existe.",
            "Moyenne convertie en GPA si la bourse le demande.",
        ),
    ),
    "uk_cv": CVFormat(
        "uk_cv", "CV britannique", "UK CV", 2,
        summary_title_fr="Profil personnel", summary_title_en="Personal statement",
        order=ATS_ORDER,
        rules=(
            "Deux pages au maximum, sans photo ni date de naissance.",
            "Un court profil personnel en tête, centré sur le projet d'études.",
            "Résultats concrets et compétences transférables mis en avant.",
        ),
    ),
    "academique": CVFormat(
        "academique", "CV académique", "Academic CV", 3,
        show_nationality=True,
        summary_title_fr="Intérêts de recherche", summary_title_en="Research interests",
        order=("education", "research", "publications", "experience", "projects", "skills", "languages", "engagement", "references"),
        rules=(
            "Formation, mémoire et travaux de recherche en premier.",
            "Publications, communications et encadrants de recherche mentionnés.",
            "La longueur suit le parcours scientifique, sans limite stricte à une page.",
        ),
    ),
}

SECTION_TITLES = {
    "fr": {
        "education": "Formation", "experience": "Expériences", "projects": "Projets", "skills": "Compétences",
        "languages": "Langues", "engagement": "Engagement associatif", "interests": "Centres d'intérêt",
        "research": "Recherche", "publications": "Publications et communications", "references": "Références",
        "personal": "Informations personnelles",
    },
    "en": {
        "education": "Education", "experience": "Experience", "projects": "Projects", "skills": "Skills",
        "languages": "Languages", "engagement": "Leadership and volunteering", "interests": "Interests",
        "research": "Research experience", "publications": "Publications and presentations", "references": "References",
        "personal": "Personal details",
    },
}
EUROPASS_TITLES = {
    "fr": {"experience": "Expérience professionnelle", "education": "Éducation et formation", "languages": "Compétences linguistiques", "skills": "Compétences numériques et techniques"},
    "en": {"experience": "Work experience", "education": "Education and training", "languages": "Language skills", "skills": "Digital and technical skills"},
}
LEBENSLAUF_TITLES = {
    "fr": {"education": "Parcours scolaire et universitaire", "experience": "Expérience professionnelle et stages", "personal": "Données personnelles"},
    "en": {"education": "Education", "experience": "Work experience and internships", "personal": "Personal data"},
}


def section_title(fmt: CVFormat, key: str, language: str) -> str:
    lang = "en" if language == "en" else "fr"
    if fmt.code == "europass" and key in EUROPASS_TITLES[lang]:
        return EUROPASS_TITLES[lang][key]
    if fmt.code == "lebenslauf" and key in LEBENSLAUF_TITLES[lang]:
        return LEBENSLAUF_TITLES[lang][key]
    return SECTION_TITLES[lang].get(key, key.capitalize())


def document_language(s: Scholarship | None, profile: Profile | None = None) -> str:
    """Langue de la candidature : celle de la bourse, sinon le français."""
    if s is None:
        return "fr"
    langs = list(s.languages or [])
    countries = set(s.study_countries or [])
    if "fr" in langs and (not countries or countries & FRENCH_SPEAKING or langs[0] == "fr"):
        return "fr"
    if langs and langs[0] == "fr":
        return "fr"
    if not langs and countries and countries <= FRENCH_SPEAKING:
        return "fr"
    return "en"


def choose_format(s: Scholarship | None, p: Profile | None) -> tuple[CVFormat, str]:
    """Retourne le format retenu et la raison, en une phrase destinée à l'étudiant."""
    if p is not None and p.target_level == "BAC7":
        return FORMATS["academique"], t("Vous visez un doctorat : le CV académique met en avant votre formation et vos travaux de recherche.", "You are aiming for a PhD: the academic CV highlights your education and research.")
    if s is None:
        return FORMATS["ats"], t("Sans bourse précise, nous appliquons le format international lisible par les logiciels de tri (ATS).", "With no specific scholarship, we use the international format that screening software (ATS) can read.")
    countries = set(s.study_countries or [])
    text = f"{s.title} {s.organization} {s.summary}".lower()
    names = ", ".join(country_name(c, "en" if is_en() else "fr") for c in sorted(countries)) if countries else ""
    if "erasmus" in text or "europass" in text:
        return FORMATS["europass"], t("Programme européen : le format Europass est celui que les jurys attendent.", "European programme: Europass is the format panels expect.")
    if len(countries) == 1:
        c = next(iter(countries))
        if c in GERMAN_SPEAKING:
            return FORMATS["lebenslauf"], t(f"Études en {names} : le Lebenslauf tabulaire et daté est l'usage local.", f"Studies in {names}: the dated, tabular Lebenslauf is the local norm.")
        if c in NORTH_AMERICA:
            return FORMATS["us_resume"], t(f"Études en {names} : le résumé d'une page, sans photo ni date de naissance, est la norme.", f"Studies in {names}: a one-page résumé with no photo or date of birth is the norm.")
        if c in UK_STYLE:
            return FORMATS["uk_cv"], t(f"Études en {names} : le CV britannique avec un profil personnel en tête est la norme.", f"Studies in {names}: a British CV opening with a personal profile is the norm.")
        if c in FRENCH_SPEAKING:
            return FORMATS["francais"], t(f"Études en {names} : le CV français d'une page est l'usage attendu.", f"Studies in {names}: a one-page French CV is what is expected.")
        if c in EU:
            return FORMATS["europass"], t(f"Études en {names} : le format Europass est reconnu par les universités européennes.", f"Studies in {names}: Europass is recognised by European universities.")
        if c in ASIA_DETAILED:
            return FORMATS["ats"], t(f"Études en {names} : format international, avec date de naissance et nationalité souvent demandées.", f"Studies in {names}: international format, with date of birth and nationality often requested.")
    if countries and countries <= EU:
        return FORMATS["europass"], t("Bourse européenne : le format Europass est reconnu dans tous les pays concernés.", "European scholarship: Europass is recognised in every country involved.")
    return FORMATS["ats"], t("Bourse ouverte à plusieurs pays : nous appliquons le format international lisible par les logiciels de tri (ATS).", "Scholarship open to several countries: we use the international format that screening software (ATS) can read.")


def letter_style(s: Scholarship | None, language: str) -> str:
    """fr | en_uk | en_us : disposition et formules de la lettre."""
    if language != "en":
        return "fr"
    countries = set((s.study_countries if s else []) or [])
    if countries and countries <= NORTH_AMERICA:
        return "en_us"
    return "en_uk"


DOMAINS_EN = {
    "agriculture": "Agriculture and agronomy", "arts": "Arts, design and architecture", "biologie": "Biology and life sciences",
    "chimie": "Chemistry", "droit": "Law and political science", "economie": "Economics and management", "education": "Education",
    "energie": "Energy and environment", "informatique": "Computer science", "ingenierie": "Engineering",
    "langues": "Languages and humanities", "mathematiques": "Mathematics and statistics", "medecine": "Medicine and health",
    "physique": "Physics", "relations_internationales": "International relations and development",
    "sciences_sociales": "Social sciences and psychology", "journalisme": "Journalism and communication", "tous": "All fields",
}
COUNTRIES_EN = {
    "DZ": "Algeria", "AO": "Angola", "BJ": "Benin", "BW": "Botswana", "BF": "Burkina Faso", "BI": "Burundi", "CM": "Cameroon",
    "CV": "Cape Verde", "CF": "Central African Republic", "TD": "Chad", "KM": "Comoros", "CG": "Republic of the Congo",
    "CD": "DR Congo", "CI": "Côte d'Ivoire", "DJ": "Djibouti", "EG": "Egypt", "GQ": "Equatorial Guinea", "ER": "Eritrea",
    "ET": "Ethiopia", "GA": "Gabon", "GM": "The Gambia", "GH": "Ghana", "GN": "Guinea", "GW": "Guinea-Bissau", "KE": "Kenya",
    "LS": "Lesotho", "LR": "Liberia", "LY": "Libya", "MG": "Madagascar", "MW": "Malawi", "ML": "Mali", "MR": "Mauritania",
    "MU": "Mauritius", "MA": "Morocco", "MZ": "Mozambique", "NA": "Namibia", "NE": "Niger", "NG": "Nigeria", "RW": "Rwanda",
    "SN": "Senegal", "SL": "Sierra Leone", "SO": "Somalia", "ZA": "South Africa", "SS": "South Sudan", "SD": "Sudan",
    "TZ": "Tanzania", "TG": "Togo", "TN": "Tunisia", "UG": "Uganda", "ZM": "Zambia", "ZW": "Zimbabwe", "HT": "Haiti",
    "FR": "France", "BE": "Belgium", "CH": "Switzerland", "DE": "Germany", "AT": "Austria", "NL": "Netherlands", "GB": "United Kingdom",
    "IE": "Ireland", "IT": "Italy", "ES": "Spain", "PT": "Portugal", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "PL": "Poland", "HU": "Hungary", "CZ": "Czechia", "US": "United States", "CA": "Canada", "AU": "Australia", "NZ": "New Zealand",
    "CN": "China", "JP": "Japan", "KR": "South Korea", "IN": "India", "TR": "Türkiye", "RU": "Russia", "AE": "United Arab Emirates",
    "SA": "Saudi Arabia", "QA": "Qatar", "BR": "Brazil", "MX": "Mexico", "TW": "Taiwan", "SG": "Singapore", "MY": "Malaysia",
}


def country_name(code: str, language: str) -> str:
    if language == "en":
        return COUNTRIES_EN.get(code) or COUNTRIES.get(code, code)
    return COUNTRIES.get(code, code)


def domain_name(code: str | None, language: str) -> str:
    from ..vocab import DOMAINS

    if not code:
        return ""
    return DOMAINS_EN.get(code, "") if language == "en" else DOMAINS.get(code, "")
