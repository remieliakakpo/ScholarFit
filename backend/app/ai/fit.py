"""Compatibilité d'une candidature avec une bourse, à vérifier AVANT de postuler.

Trois volets :
1. conditions d'accès (niveau, nationalité, âge, domaine, moyenne, test de langue, date limite) ;
2. dossier (CV importé, lettre, pièces demandées) ;
3. adéquation du CV avec ce que le jury valorise (thèmes de la bourse, mots-clés du domaine).

Le résultat donne un score, un verdict et des améliorations concrètes, classées par priorité.
"""
from __future__ import annotations

from datetime import date

from ..deadlines import deadline_info
from ..matching import Criteria, hard_filter, language_ok, score
from ..models import Application, Profile, Scholarship
from ..vocab import DOMAINS, LEVELS, expand_nationalities
from . import writing
from ..i18n import is_en, t
from .client import ask_json
from .cv import THEMES, diagnose_rules, theme_advice, theme_coverage, theme_label
from .formats import DOMAINS_EN

REQUIREMENT_LABELS_EN = {
    "cv": "CV", "lettre": "Cover letter", "recommandation": "Recommendation letters", "releves": "Transcripts",
    "test_langue": "Language test", "diplomes": "Copies of diplomas", "passeport": "Passport", "projet_recherche": "Research proposal",
    "lettre_admission": "Admission letter", "certificat_medical": "Medical certificate", "portfolio": "Portfolio",
}
REQUIREMENT_LABELS = {
    "cv": "CV", "lettre": "Lettre de motivation", "recommandation": "Lettres de recommandation", "releves": "Relevés de notes",
    "test_langue": "Test de langue", "diplomes": "Copies des diplômes", "passeport": "Passeport", "projet_recherche": "Projet de recherche",
    "lettre_admission": "Lettre d'admission", "certificat_medical": "Certificat médical", "portfolio": "Portfolio",
}


def _check(key: str, label: str, status: str, detail: str) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail}


def fit_check(p: Profile, s: Scholarship, application: Application | None, use_ai: bool = False, today: date | None = None) -> dict:
    today = today or date.today()
    c = Criteria.from_profile(p, today)
    checks: list[dict] = []
    improvements: list[dict] = []

    # 1. Conditions d'accès
    if s.levels:
        if not c.target_level:
            checks.append(_check("niveau", t("Niveau d'études", "Level of study"), "inconnu", t("Indiquez le diplôme visé dans votre profil.", "Add your target degree to your profile.")))
        elif c.target_level in s.levels:
            checks.append(_check("niveau", t("Niveau d'études", "Level of study"), "ok", t(f"La bourse finance votre niveau ({LEVELS.get(c.target_level, c.target_level)}).", "The scholarship funds your level of study.")))
        else:
            checks.append(_check("niveau", t("Niveau d'études", "Level of study"), "ko", t("La bourse ne finance pas le diplôme que vous visez.", "The scholarship does not fund the degree you are aiming for.")))
    if c.nationalities:
        allowed = expand_nationalities(s.eligible_nationalities or [])
        excluded = expand_nationalities(s.excluded_nationalities) if s.excluded_nationalities else set()
        ok = [n for n in c.nationalities if (allowed is None or n in allowed) and n not in (excluded or set())]
        checks.append(_check("nationalite", t("Nationalité", "Nationality"), "ok" if ok else "ko", t("Votre nationalité est éligible.", "Your nationality is eligible.") if ok else t("Votre nationalité ne fait pas partie des pays éligibles.", "Your nationality is not among the eligible countries.")))
    else:
        checks.append(_check("nationalite", t("Nationalité", "Nationality"), "inconnu", t("Ajoutez votre nationalité à votre profil.", "Add your nationality to your profile.")))
    if s.max_age:
        if c.age is None:
            checks.append(_check("age", t("Âge", "Age"), "inconnu", t(f"Âge maximum {s.max_age} ans : ajoutez votre date de naissance.", f"Maximum age {s.max_age}: add your date of birth.")))
        else:
            checks.append(_check("age", t("Âge", "Age"), "ok" if c.age <= s.max_age else "ko", t(f"Âge maximum {s.max_age} ans, vous avez {c.age} ans.", f"Maximum age {s.max_age}, you are {c.age}.")))
    if s.domains and "tous" not in s.domains:
        if not c.domain:
            checks.append(_check("domaine", t("Domaine", "Field"), "inconnu", t("Indiquez votre domaine d'études.", "Add your field of study.")))
        else:
            okd = c.domain in s.domains
            names = ", ".join((DOMAINS_EN if is_en() else DOMAINS).get(d, d) for d in s.domains[:4])
            checks.append(_check("domaine", t("Domaine", "Field"), "ok" if okd else "ko", t(f"Domaines financés : {names}.", f"Funded fields: {names}.")))
    if s.min_grade is not None:
        if c.grade_average is None:
            checks.append(_check("moyenne", t("Moyenne", "Grades"), "inconnu", t(f"Minimum demandé : {s.min_grade:g}/20. Ajoutez votre moyenne.", f"Required minimum: {s.min_grade:g}/20. Add your average grade.")))
        else:
            checks.append(_check("moyenne", t("Moyenne", "Grades"), "ok" if c.grade_average >= s.min_grade else "ko", t(f"Minimum {s.min_grade:g}/20, votre moyenne {c.grade_average:g}/20.", f"Minimum {s.min_grade:g}/20, your average {c.grade_average:g}/20.")))
    lang, msg = language_ok(s, c)
    if lang is not None:
        checks.append(_check("langue", t("Test de langue", "Language test"), "ok" if lang else "ko", (msg or "")[:1].upper() + (msg or "")[1:] + "."))
    if s.target_groups:
        okg = bool(set(s.target_groups) & set(c.situations))
        checks.append(_check("public", t("Public visé", "Target group"), "ok" if okg else "ko", t("Vous faites partie du public visé.", "You belong to the target group.") if okg else t("La bourse est réservée à un public précis.", "The scholarship is reserved for a specific group.")))
    info = deadline_info(s, today)
    if info.status == "expiree":
        checks.append(_check("date", t("Date limite", "Deadline"), "ko", t("La date limite de cette session est passée.", "The deadline for this round has passed.")))
    elif info.days_left is not None:
        st = "attention" if info.days_left <= 30 else "ok"
        checks.append(_check("date", t("Date limite", "Deadline"), st, t(f"{info.days_left} jour(s) pour déposer votre dossier.", f"{info.days_left} day(s) left to apply.")))

    blocking = [x for x in checks if x["status"] == "ko"]
    unknown = [x for x in checks if x["status"] == "inconnu"]
    for x in unknown:
        improvements.append({"priority": 1, "text": x["detail"], "action": "profil"})

    # 2. Dossier
    reqs = list(s.requirements or ["cv", "lettre"])
    docs = []
    for r in reqs:
        have = False
        if r == "cv":
            have = bool(p.cv_text)
        elif r == "lettre":
            have = bool(application and application.letter)
        elif r == "test_langue":
            have = bool(p.language_scores)
        elif application and application.checklist:
            have = bool(application.checklist.get(r))
        docs.append({"key": r, "label": (REQUIREMENT_LABELS_EN if is_en() else REQUIREMENT_LABELS).get(r, r.replace("_", " ").capitalize()), "ready": have})
    if not p.cv_text:
        improvements.append({"priority": 1, "text": t("Importez votre CV : il sert au diagnostic, à la version adaptée et à la lettre.", "Upload your CV: it feeds the assessment, the tailored version and the letter."), "action": "cv"})
    if "lettre" in reqs and not (application and application.letter):
        improvements.append({"priority": 2, "text": t("Rédigez la lettre de motivation propre à cette bourse.", "Write the cover letter for this scholarship."), "action": "lettre"})

    # 3. Adéquation du CV
    covered, missing = theme_coverage(s, p.cv_text or "", p)
    themes = [{"key": k, "label": theme_label(k), "covered": k in covered} for k in covered + missing]
    for k in missing:
        improvements.append({"priority": 2, "text": theme_advice(k), "action": "cv"})
    cv_score = None
    if p.cv_text:
        diag = diagnose_rules(p.cv_text, p, s)
        cv_score = diag["score"]
        for crit in sorted(diag["criteria"], key=lambda x: x["score"]):
            if crit["recommendation"] and crit["score"] < 70 and crit["key"] != "adequation":
                improvements.append({"priority": 3, "text": crit["recommendation"], "action": "cv"})
                if sum(1 for i in improvements if i["priority"] == 3) >= 3:
                    break

    # Score global : conditions (40), adéquation du profil (30), CV (20), dossier (10)
    if blocking:
        overall = min(35, int(score(s, c, today).score * 0.35))
    else:
        match = score(s, c, today).score
        eligibility = 40 if not unknown else 40 - 8 * len(unknown)
        theme_part = 30 * (len(covered) / max(1, len(covered) + len(missing))) if (covered or missing) else 30 * match / 100
        cv_part = 20 * (cv_score or 0) / 100
        docs_part = 10 * (sum(1 for d in docs if d["ready"]) / max(1, len(docs)))
        overall = int(round(max(0, eligibility) + theme_part + cv_part + docs_part))
    if blocking:
        verdict = t("Conditions non remplies", "Eligibility not met")
        verdict_detail = t("Une ou plusieurs conditions d'accès ne sont pas remplies : votre dossier risque d'être écarté sans être lu.", "One or more eligibility conditions are not met: your application may be rejected without being read.")
        level = "ko"
    elif overall >= 75:
        verdict = t("Dossier prêt", "Application ready")
        verdict_detail = t("Votre profil correspond à la bourse. Relisez votre lettre une dernière fois et déposez votre dossier.", "Your profile matches the scholarship. Reread your letter one last time and submit your application.")
        level = "ok"
    elif overall >= 50:
        verdict = t("À renforcer avant l'envoi", "Strengthen before applying")
        verdict_detail = t("Vous êtes éligible. Les améliorations ci-dessous augmenteront nettement vos chances.", "You are eligible. The improvements below will clearly raise your chances.")
        level = "moyen"
    else:
        verdict = t("Dossier à construire", "Application to build")
        verdict_detail = t("Complétez votre profil et votre CV, puis adaptez-les à cette bourse avant de postuler.", "Complete your profile and CV, then tailor them to this scholarship before applying.")
        level = "faible"
    for b in blocking:
        improvements.insert(0, {"priority": 0, "text": b["detail"], "action": "conditions"})

    improvements.sort(key=lambda i: i["priority"])
    seen, unique = set(), []
    for i in improvements:
        if i["text"] not in seen:
            seen.add(i["text"])
            unique.append(i)

    result = {
        "score": overall, "verdict": verdict, "verdict_detail": verdict_detail, "level": level,
        "checks": checks, "documents": docs, "themes": themes, "cv_score": cv_score,
        "improvements": unique[:8], "ai_used": False,
    }
    if use_ai and p.cv_text and not blocking:
        _ai_advice(result, p, s)
    return result


ADVICE_SCHEMA = {
    "type": "object",
    "properties": {"advice": {"type": "array", "items": {"type": "string"}}},
    "required": ["advice"],
    "additionalProperties": False,
}
ADVICE_SYSTEM_BASE = """Vous êtes conseiller en candidatures de bourses. À partir du profil, du CV et de la description de la
bourse, donnez 3 à 5 améliorations concrètes que l'étudiant peut faire AVANT de déposer son dossier pour
correspondre davantage à ce que le jury recherche. Chaque conseil tient en une ou deux phrases complètes,
au vouvoiement, cite un élément précis du CV ou de la bourse, et ne suppose aucun fait absent du CV.
Pas de tiret cadratin, pas de formule creuse."""


def _ai_advice(result: dict, p: Profile, s: Scholarship) -> None:
    user = f"""BOURSE : {s.title} ({s.organization})
{s.summary}
Conditions : {'; '.join(s.eligibility or [])}

PROFIL : projet = {p.project or '-'} ; domaine = {DOMAINS.get(p.domain or '', '-')}

CV
{(p.cv_text or '')[:9000]}"""
    system = ADVICE_SYSTEM_BASE + ("\nRédigez les conseils en anglais." if is_en() else "")
    data = ask_json(system, user, ADVICE_SCHEMA, effort="medium", max_tokens=3000, cache=True)
    if not data or not data.get("advice"):
        return
    ai_items = [{"priority": 2, "text": writing.complete_sentence(writing.clean_punctuation(a)), "action": "cv"} for a in data["advice"][:5]]
    keep = [i for i in result["improvements"] if i["priority"] <= 1]
    result["improvements"] = (keep + ai_items)[:8]
    result["ai_used"] = True


def is_blocked(p: Profile, s: Scholarship) -> str | None:
    return hard_filter(s, Criteria.from_profile(p), date.today())
