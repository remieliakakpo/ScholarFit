"""Moteur de matching profil / bourses, en trois passes :

1. filtres durs : on exclut tout ce à quoi l'étudiant n'a pas droit ;
2. score de pertinence de 0 à 100 (pondérations ajustables ci-dessous) ;
3. explication lisible : pourquoi ça correspond, ce qui manque, date limite.

Le même moteur sert à la page « Mes bourses » et à l'assistant de recherche (chat).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from . import i18n
from .deadlines import deadline_info
from .i18n import t
from .geo import countries_in
from .models import Profile, Scholarship
from .vocab import COUNTRIES, DOMAINS, LEVELS, expand_nationalities

WEIGHTS = {
    "domain": 30,
    "semantic": 25,
    "grades_languages": 20,
    "country": 15,
    "funding": 10,
}

SITUATION_LABELS = {
    "refugie": "statut de réfugié",
    "handicap": "situation de handicap",
    "revenus_modestes": "revenus modestes",
    "premiere_generation": "première génération à l'université",
    "femmes": "candidates femmes",
}
SITUATION_LABELS_EN = {
    "refugie": "refugee status",
    "handicap": "disability",
    "revenus_modestes": "low household income",
    "premiere_generation": "first generation at university",
    "femmes": "women applicants",
}


def situation_labels() -> dict[str, str]:
    return i18n.loc(SITUATION_LABELS, SITUATION_LABELS_EN)


@dataclass
class Criteria:
    """Critères de recherche : construits depuis un profil ou depuis le chat."""

    target_level: str | None = None
    nationalities: list[str] = field(default_factory=list)
    age: int | None = None
    domain: str | None = None
    wished_countries: list[str] = field(default_factory=list)
    wished_regions: list[str] = field(default_factory=list)  # vide = partout dans le monde
    grade_average: float | None = None
    language_scores: dict[str, float] = field(default_factory=dict)
    languages: list[str] = field(default_factory=list)
    project_text: str = ""
    full_funding_only: bool = False
    situations: list[str] = field(default_factory=list)
    deadline_after: date | None = None
    experience_years: float | None = None
    experience_declared: bool = False  # True : saisie par l'étudiant ; False : estimée d'après le CV

    @classmethod
    def from_profile(cls, p: Profile, today: date | None = None) -> "Criteria":
        today = today or date.today()
        declared = getattr(p, "work_experience_years", None)
        return cls(
            experience_years=declared if declared is not None else estimate_experience_years(p.cv_text, today),
            experience_declared=declared is not None,
            target_level=p.target_level,
            nationalities=list(p.nationalities or []),
            age=age_on(p.birth_date, today) if p.birth_date else None,
            domain=p.domain,
            wished_countries=list(p.wished_countries or []),
            wished_regions=list(p.wished_regions or []),
            grade_average=p.grade_average,
            language_scores=dict(p.language_scores or {}),
            languages=list((p.languages or {}).keys()),
            project_text=" ".join(filter(None, [p.project, p.experiences, p.engagement, p.cv_text or ""]))[:4000],
            full_funding_only=bool(p.full_funding_only),
            situations=list(p.situations or []),
        )

    def destination_countries(self) -> set[str]:
        """Pays visés : pays cités + pays des régions choisies. Vide = partout."""
        out = set(self.wished_countries)
        for r in self.wished_regions:
            out |= countries_in(r)
        return out

    def strict_destination(self) -> set[str]:
        """Pays qui comptent pour trier les résultats : les pays précis s'il y en a, sinon ceux des continents."""
        if self.wished_countries:
            return set(self.wished_countries)
        out: set[str] = set()
        for r in self.wished_regions:
            out |= countries_in(r)
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "Criteria":
        return cls(
            target_level=d.get("target_level"),
            nationalities=list(d.get("nationalities") or []),
            age=d.get("age"),
            domain=d.get("domain"),
            wished_countries=list(d.get("wished_countries") or []),
            wished_regions=list(d.get("wished_regions") or []),
            grade_average=d.get("grade_average"),
            language_scores=dict(d.get("language_scores") or {}),
            languages=list(d.get("languages") or []),
            project_text=d.get("project_text") or "",
            full_funding_only=bool(d.get("full_funding_only")),
            situations=list(d.get("situations") or []),
            deadline_after=date.fromisoformat(d["deadline_after"]) if d.get("deadline_after") else None,
            experience_years=d.get("work_experience_years"),
            experience_declared=d.get("work_experience_years") is not None,
        )


@dataclass
class MatchResult:
    scholarship: Scholarship
    score: int
    chance: str
    reasons: list[str]
    gaps: list[str]
    days_left: int | None


_MONTHS_RE = {"jan": 1, "fév": 2, "fev": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4, "mai": 5, "may": 5, "juin": 6, "jun": 6,
              "juil": 7, "jul": 7, "aoû": 8, "aou": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}
_RANGE = re.compile(r"(?:([a-zéû]{3,9})\.?\s+)?((?:19|20)\d{2})\s*[-–—à]+\s*(?:(?:([a-zéû]{3,9})\.?\s+)?((?:19|20)\d{2})|(aujourd'hui|aujourd’hui|présent|present|now|en cours|current))", re.I)


def _month(word: str | None, default: int) -> int:
    if not word:
        return default
    w = word.lower()
    return next((v for k, v in _MONTHS_RE.items() if w.startswith(k)), default)


def estimate_experience_years(cv_text: str | None, today: date | None = None) -> float | None:
    """Années d'expérience professionnelle estimées d'après les périodes de la rubrique « Expérience » du CV
    (stages compris, périodes qui se chevauchent comptées une fois). None si le CV n'en dit rien."""
    if not cv_text:
        return None
    today = today or date.today()
    lines = cv_text.splitlines()
    in_exp, months = False, set()
    for line in lines:
        bare = line.strip()
        if bare and len(bare) < 45 and (bare.isupper() or bare.endswith(":")):
            low = bare.lower()
            in_exp = any(w in low for w in ("expérience", "experience", "emploi", "employment", "parcours professionnel", "stages"))
            continue
        if not in_exp:
            continue
        for m in _RANGE.finditer(line):
            y1, y2 = int(m.group(2)), (today.year if m.group(5) else int(m.group(4)))
            m1 = _month(m.group(1), 1)
            m2 = today.month if m.group(5) else _month(m.group(3), 12 if not m.group(3) else 1)
            a, b = y1 * 12 + m1, min(y2 * 12 + m2, today.year * 12 + today.month)
            months.update(range(a, b + 1))
    if not months:
        return None
    return round(len(months) / 12, 1)


def age_on(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def missing_minimum(c: Criteria) -> list[str]:
    """Profil minimum = nationalité, âge, niveau visé, domaine."""
    missing = []
    if not c.nationalities:
        missing.append(t("nationalité", "nationality"))
    if c.age is None:
        missing.append(t("âge", "age"))
    if not c.target_level:
        missing.append(t("niveau visé", "target level"))
    if not c.domain:
        missing.append(t("domaine", "field of study"))
    return missing


# ---------------------------------------------------------------- passe 1
def hard_filter(s: Scholarship, c: Criteria, today: date) -> str | None:
    """Retourne la raison d'exclusion, ou None si la bourse est accessible."""
    if deadline_info(s, today).status == "expiree":
        return t("date limite dépassée", "deadline passed")
    if c.deadline_after and s.deadline and s.deadline < c.deadline_after:
        return t("date limite trop proche", "deadline too close")
    if c.target_level and s.levels and c.target_level not in s.levels:
        return "niveau"
    if c.nationalities:
        allowed = expand_nationalities(s.eligible_nationalities or [])
        excluded = expand_nationalities(s.excluded_nationalities) if s.excluded_nationalities else set()
        ok = [n for n in c.nationalities if (allowed is None or n in allowed) and n not in (excluded or set())]
        if not ok:
            return "nationalité"
    if s.max_age and c.age is not None and c.age > s.max_age:
        return "âge"
    if s.min_experience_years and c.experience_declared and c.experience_years is not None and c.experience_years < s.min_experience_years:
        return t("expérience professionnelle", "work experience")
    dest = c.destination_countries()
    if dest and s.study_countries and not set(s.study_countries) & dest:
        return t("pays d'étude", "study country")
    if c.full_funding_only and not s.full_funding:
        return t("financement partiel", "partial funding")
    if s.target_groups and not set(s.target_groups) & set(c.situations):
        return t("public ciblé", "target group")
    return None


# ---------------------------------------------------------------- passe 2
_STOP = set(
    "le la les de des du un une et en au aux pour par sur dans avec ou a l d the of and in for to on with "
    "je tu il elle nous vous ils mon ma mes son sa ses est sont etre être plus master licence doctorat "
    "bourse bourses etude etudes étude études programme".split()
)


def _tokens(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = re.findall(r"[a-z]{3,}", text)
    # racine grossière : on coupe les terminaisons fréquentes
    return {w[:7] for w in words if w not in _STOP}


def semantic_similarity(a: str, b: str) -> float:
    """Similarité par recouvrement de mots (0 à 1). Pour la V2 : embeddings + pgvector."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb), 25)


def language_ok(s: Scholarship, c: Criteria) -> tuple[bool | None, str | None]:
    if not s.language_tests:
        return None, None
    for test, minimum in s.language_tests.items():
        if c.language_scores.get(test, -1) >= minimum:
            return True, t(f"votre {test} ({c.language_scores[test]}) atteint le minimum demandé",
                            f"your {test} score ({c.language_scores[test]}) meets the required minimum")
    demanded = t(" ou ", " or ").join(f"{k} {m:g}" for k, m in s.language_tests.items())
    return False, t(f"un test de langue est demandé : {demanded}", f"a language test is required: {demanded}")


def score(s: Scholarship, c: Criteria, today: date) -> MatchResult:
    reasons: list[str] = []
    gaps: list[str] = []
    total = 0.0

    # Domaine (30)
    if c.domain and c.domain in (s.domains or []):
        total += WEIGHTS["domain"]
        dom = i18n.loc(DOMAINS, i18n.DOMAINS_EN).get(c.domain, c.domain)
        reasons.append(t(f"elle finance votre domaine ({dom})", f"it funds your field ({dom})"))
    elif "tous" in (s.domains or []):
        total += WEIGHTS["domain"] * 0.65
        reasons.append(t("elle est ouverte à tous les domaines", "it is open to all fields"))

    # Similarité projet / description (25)
    sim = semantic_similarity(c.project_text, f"{s.title} {s.summary}") if c.project_text else 0.0
    total += WEIGHTS["semantic"] * min(1.0, 0.35 + sim) if c.project_text else WEIGHTS["semantic"] * 0.35
    if sim >= 0.3:
        reasons.append(t("votre projet rejoint les objectifs de la bourse", "your project matches the goals of the scholarship"))

    # Notes et langues (20)
    part = 0.5
    blocking = 0
    if s.min_grade is not None:
        if c.grade_average is None:
            gaps.append(t(f"moyenne minimum demandée : {s.min_grade:g}/20 (ajoutez votre moyenne au profil)",
                           f"minimum average required: {s.min_grade:g}/20 (add your average to your profile)"))
        elif c.grade_average >= s.min_grade:
            part += 0.25
            reasons.append(t(f"votre moyenne ({c.grade_average:g}/20) dépasse le minimum de {s.min_grade:g}/20",
                             f"your average ({c.grade_average:g}/20) is above the minimum of {s.min_grade:g}/20"))
        else:
            part -= 0.5
            blocking += 1
            gaps.append(t(f"votre moyenne ({c.grade_average:g}/20) est sous le minimum de {s.min_grade:g}/20",
                          f"your average ({c.grade_average:g}/20) is below the minimum of {s.min_grade:g}/20"))
    if s.min_experience_years:
        need = s.min_experience_years
        need_txt = f"{need:g} an{'s' if need >= 2 else ''}"
        if c.experience_years is None:
            gaps.append(t(f"il faut au moins {need_txt} d'expérience professionnelle : indiquez la vôtre dans votre profil",
                          f"at least {need:g} year{'s' if need >= 2 else ''} of work experience required: add yours to your profile"))
        elif c.experience_years >= need:
            reasons.append(t(f"vous avez l'expérience professionnelle demandée ({need_txt} minimum)",
                             f"you have the work experience required ({need:g} years minimum)"))
        else:
            blocking += 1
            part -= 0.25
            have = f"{c.experience_years:g}".replace(".", ",")
            gaps.append(t(f"il faut au moins {need_txt} d'expérience professionnelle ; votre CV en montre environ {have} : vérifiez avant de candidater",
                          f"at least {need:g} years of work experience required; your CV shows about {c.experience_years:g}: check before applying"))
    lang, msg = language_ok(s, c)
    if lang is True:
        part += 0.25
        reasons.append(msg)
    elif lang is False:
        part -= 0.25
        blocking += 1
        gaps.append(msg)
    elif s.languages and c.languages and set(s.languages) & set(c.languages):
        part += 0.25
    total += WEIGHTS["grades_languages"] * max(0.0, min(1.0, part))

    # Pays (15)
    dest = c.destination_countries()
    if dest and set(s.study_countries or []) & dest:
        common = set(s.study_countries) & dest
        exact = common & set(c.wished_countries)
        total += WEIGHTS["country"] * (1.0 if exact or not c.wished_countries else 0.8)
        table = i18n.countries(COUNTRIES)
        names = ", ".join(table.get(x, x) for x in sorted(exact or common))
        reasons.append(t(f"elle permet d'étudier dans un pays que vous visez ({names})",
                         f"it lets you study in a country you are aiming for ({names})"))
    elif not s.study_countries:
        total += WEIGHTS["country"] * 0.6
    else:
        total += WEIGHTS["country"] * (0.5 if not dest else 0.2)

    # Financement (10)
    if s.full_funding:
        total += WEIGHTS["funding"]
        reasons.append(t("le financement est complet", "it is fully funded"))
    elif s.amount:
        total += WEIGHTS["funding"] * 0.5

    if s.target_groups and set(s.target_groups) & set(c.situations):
        reasons.append(t("elle est réservée à un public dont vous faites partie", "it is reserved for a group you belong to"))

    info = deadline_info(s, today)
    days_left = info.days_left
    if info.status == "urgente":
        plural = "s" if (days_left or 0) > 1 else ""
        gaps.append(t(f"date limite dans {days_left} jour{plural} : priorité absolue",
                      f"deadline in {days_left} day{plural}: top priority"))
    elif info.status == "bientot":
        gaps.append(t(f"date limite dans {days_left} jours : commencez votre dossier maintenant",
                      f"deadline in {days_left} days: start your application now"))

    final = int(round(total))
    if final >= 70 and not blocking:
        chance = "bonne"
    elif final < 50 or blocking >= 2:
        chance = "faible"
    else:
        chance = "moyenne"

    return MatchResult(s, final, chance, reasons, gaps, days_left)


def widen_hint(count: int, c: Criteria) -> str | None:
    """Conseil affiché quand il y a moins de 10 résultats."""
    if count >= 10:
        return None
    tips = []
    if c.wished_countries or c.wished_regions:
        tips.append(t("ajoutez d'autres pays ou choisissez « partout dans le monde »", "add other countries or choose \"anywhere in the world\""))
    if c.full_funding_only:
        tips.append(t("acceptez aussi les bourses partielles", "also accept partial scholarships"))
    if not c.languages:
        tips.append(t("indiquez les langues que vous parlez", "add the languages you speak"))
    tips.append(t("consultez aussi les bourses à préparer pour la prochaine session", "also look at the scholarships to prepare for the next round"))
    return t("Peu de bourses correspondent à tous vos critères. Pour en voir davantage : ", "Few scholarships match all your criteria. To see more: ") + " ; ".join(tips) + "."


def next_session(scholarships: list[Scholarship], c: Criteria, today: date | None = None, limit: int = 12) -> list[MatchResult]:
    """Bourses annuelles dont la session est close mais qui conviendraient au profil : à préparer pour l'an prochain."""
    today = today or date.today()
    out = []
    for s in scholarships:
        if not s.recurring or deadline_info(s, today).status != "expiree":
            continue
        reason = hard_filter(s, c, today.replace(year=today.year - 5))  # on ignore la date limite, pas les autres critères
        if reason and reason not in (t("date limite dépassée", "deadline passed"),):
            continue
        out.append(score(s, c, today))
    out.sort(key=lambda m: m.score, reverse=True)
    return out[:limit]


def rank(scholarships: list[Scholarship], c: Criteria, today: date | None = None, limit: int = 50) -> tuple[list[MatchResult], int]:
    """Applique les trois passes. Retourne (résultats triés, nombre de bourses exclues)."""
    today = today or date.today()
    kept, excluded = [], 0
    for s in scholarships:
        if hard_filter(s, c, today):
            excluded += 1
            continue
        kept.append(score(s, c, today))

    def sort_key(m: MatchResult) -> float:
        # Le tri combine le score et l'urgence : une date limite proche remonte un peu.
        urgency = 0.0
        if m.days_left is not None:
            urgency = max(0.0, 10 - m.days_left / 18)  # jusqu'à +10 pour une date dans les jours qui viennent
        return m.score + urgency

    kept.sort(key=sort_key, reverse=True)
    return kept[:limit], excluded


def profile_completeness(p: Profile) -> tuple[int, str | None]:
    checks = {
        "full_name": bool(p.full_name),
        "birth_date": bool(p.birth_date),
        "nationalities": bool(p.nationalities),
        "residence_country": bool(p.residence_country),
        "current_level": bool(p.current_level),
        "target_level": bool(p.target_level),
        "domain": bool(p.domain),
        "grade_average": p.grade_average is not None,
        "wished_countries": bool(p.wished_countries),
        "languages": bool(p.languages),
        "language_scores": bool(p.language_scores),
        "experiences": bool(p.experiences),
        "project": bool(p.project),
        "cv": bool(p.cv_text),
    }
    pct = int(round(100 * sum(checks.values()) / len(checks)))
    tip = None
    if not checks["language_scores"]:
        tip = t("Ajoutez votre score de langue (IELTS, TOEFL, DELF…) : beaucoup de bourses en demandent un.",
                "Add your language test score (IELTS, TOEFL, DELF…): many scholarships require one.")
    elif not checks["grade_average"]:
        tip = t("Ajoutez votre moyenne : certaines bourses fixent un minimum.", "Add your grade average: some scholarships set a minimum.")
    elif not checks["cv"]:
        tip = t("Importez votre CV pour un meilleur matching et des lettres plus personnelles.",
                "Upload your CV for better matching and more personal letters.")
    elif not checks["project"]:
        tip = t("Décrivez votre projet professionnel en quelques lignes : il sert au matching et aux lettres.",
                "Describe your career plan in a few lines: it is used for matching and for your letters.")
    return pct, tip


def level_label(code: str | None) -> str:
    return i18n.loc(LEVELS, i18n.LEVELS_EN).get(code or "", code or "?")
