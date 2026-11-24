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

    @classmethod
    def from_profile(cls, p: Profile, today: date | None = None) -> "Criteria":
        today = today or date.today()
        return cls(
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
        )


@dataclass
class MatchResult:
    scholarship: Scholarship
    score: int
    chance: str
    reasons: list[str]
    gaps: list[str]
    days_left: int | None


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
