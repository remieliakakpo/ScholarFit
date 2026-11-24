"""CV : diagnostic selon des critères définis, puis version adaptée à la bourse et au pays.

Diagnostic (gratuit, illimité) : neuf critères notés de 0 à 100, chacun avec un constat et
une recommandation. Les critères objectifs (coordonnées, dates, longueur, langues) sont
calculés par règles ; avec l'IA, les critères rédactionnels sont affinés et l'orthographe
est relue.

Version adaptée (comptée dans un dossier, voir ``app/credits.py``) : CV structuré, au
format du pays d'études (voir ``formats.py``), réordonné et reformulé pour la bourse visée.
"""
from __future__ import annotations

import re
from datetime import date

from ..i18n import is_en, t
from ..models import Profile, Scholarship
from ..vocab import COUNTRIES, DOMAINS
from . import writing
from .client import ask_json
from .documents import SECTION_KEYS, split_sections
from .formats import CVFormat, choose_format, country_name, document_language, domain_name, section_title

ACTION_VERBS_FR = [
    "organisé", "dirigé", "piloté", "créé", "conçu", "développé", "mené", "coordonné", "animé", "géré",
    "réalisé", "lancé", "amélioré", "analysé", "encadré", "formé", "rédigé", "présenté", "négocié",
    "mis en place", "optimisé", "fondé", "accompagné", "enseigné", "programmé", "construit", "réduit",
    "augmenté", "obtenu", "remporté", "assuré", "contribué", "conduit", "élaboré", "supervisé", "étudié",
    "collecté", "modélisé", "testé", "déployé", "automatisé", "sensibilisé", "mobilisé", "recruté",
    "participé", "évalué", "traduit", "publié", "représenté", "conseillé", "produit", "installé",
]
ACTION_VERBS_EN = [
    "led", "built", "created", "managed", "designed", "developed", "organized", "organised", "launched",
    "improved", "analyzed", "analysed", "taught", "coordinated", "conducted", "delivered", "wrote", "trained",
    "founded", "implemented", "increased", "reduced", "won", "achieved", "supervised", "mentored", "researched",
    "collected", "modelled", "modeled", "tested", "deployed", "automated", "raised", "recruited", "presented",
    "published", "represented", "produced", "established", "facilitated", "supported", "assisted",
]
ACTION_VERBS = ACTION_VERBS_FR + ACTION_VERBS_EN

# Débuts de ligne faibles et verbe d'action proposé. Le complément (« de la refonte ») est
# converti ensuite par _object_after() : « Responsable de la refonte » devient « Piloté la refonte ».
WEAK_STARTS = {
    r"^(j'ai )?(été )?responsable\s+": "Piloté",
    r"^(j'ai )?(été )?charg[ée]e?\s+": "Assuré",
    r"^participation\s+": "Participé",
    r"^aide\s+(à|a)\s+": "Accompagné",
    r"^j'ai fait\s+": "Réalisé",
    r"^j'ai travaill[ée]\s+(sur|dans)\s+": "Travaillé sur",
    r"^gestion\s+": "Géré",
    r"^organisation\s+": "Organisé",
    r"^cr[ée]ation\s+": "Créé",
    r"^d[ée]veloppement\s+": "Développé",
    r"^r[ée]daction\s+": "Rédigé",
    r"^animation\s+": "Animé",
    r"^conception\s+": "Conçu",
    r"^mise en place\s+": "Mis en place",
    r"^encadrement\s+": "Encadré",
    r"^coordination\s+": "Coordonné",
    r"^formation\s+(d[eu']|des)\s*": "Formé",
    r"^j'ai\s+": "",
    r"^i was responsible for\s+": "Led",
    r"^responsible for\s+": "Led",
    r"^in charge of\s+": "Managed",
    r"^helped (to )?": "Supported",
    r"^worked on\s+": "Delivered",
}


def _object_after(verb: str, rest: str) -> str:
    """« de la refonte » → « la refonte », « du site » → « le site », « d'une appli » → « une appli »."""
    r = rest.strip()
    if verb in ("Participé",):
        r = re.sub(r"^(à|a)\s+", "", r, flags=re.I)
        r = re.sub(r"^(la |l')", lambda m: "à " + m.group(1), r, flags=re.I) if re.match(r"^(la |l')", r, re.I) else re.sub(r"^le ", "au ", re.sub(r"^les ", "aux ", r, flags=re.I), flags=re.I)
        if not re.match(r"^(à|au|aux) ", r, re.I):
            r = "à " + r
        return r
    if verb in ("Formé",):
        return r
    for pat, rep in ((r"^de la ", "la "), (r"^de l'", "l'"), (r"^du ", "le "), (r"^des ", "les "), (r"^d'", ""), (r"^de ", ""), (r"^à la ", "la "), (r"^au ", "le "), (r"^aux ", "les ")):
        if re.match(pat, r, re.I):
            return re.sub(pat, rep, r, count=1, flags=re.I)
    return r


def apply_weak_start(line: str) -> str | None:
    """Réécrit un début de ligne faible, ou None si la ligne commence déjà bien."""
    low = line.lower()
    for pat, verb in WEAK_STARTS.items():
        m = re.match(pat, low)
        if not m:
            continue
        rest = line[m.end():].strip()
        if not rest or len(rest.split()) < 2:
            return None
        obj = _object_after(verb, rest) if verb else rest
        out = f"{verb} {writing.lower_first(obj)}".strip() if verb else obj
        out = writing.clean_punctuation(out).rstrip(".;")
        return out[:1].upper() + out[1:]
    return None

LEVEL_NOUN = {
    "fr": {"BAC": "Licence", "BAC3": "Licence", "BAC5": "Master", "BAC7": "Doctorat"},
    "en": {"BAC": "Undergraduate studies", "BAC3": "Bachelor's degree", "BAC5": "Master's degree", "BAC7": "PhD"},
}
LANG_NAMES = {
    "fr": {"fr": "Français", "en": "Anglais", "de": "Allemand", "es": "Espagnol", "pt": "Portugais", "ar": "Arabe", "zh": "Chinois", "it": "Italien", "ru": "Russe", "ja": "Japonais", "ko": "Coréen", "nl": "Néerlandais", "tr": "Turc", "sw": "Swahili", "ha": "Haoussa", "wo": "Wolof", "ee": "Éwé"},
    "en": {"fr": "French", "en": "English", "de": "German", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic", "zh": "Chinese", "it": "Italian", "ru": "Russian", "ja": "Japanese", "ko": "Korean", "nl": "Dutch", "tr": "Turkish", "sw": "Swahili", "ha": "Hausa", "wo": "Wolof", "ee": "Ewe"},
}
LEVEL_WORDS = {
    "fr": {"natif": "langue maternelle", "maternelle": "langue maternelle", "courant": "courant", "bilingue": "bilingue"},
    "en": {"natif": "native", "maternelle": "native", "courant": "fluent", "bilingue": "bilingual"},
}

EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
YEAR = r"(?:19[6-9]\d|20[0-4]\d)"
MONTH = r"(?:janv?\.?|f[ée]vr?\.?|mars|avr\.?|mai|juin|juil\.?|ao[ûu]t|sept?\.?|oct\.?|nov\.?|d[ée]c\.?|jan\.?|feb\.?|mar\.?|apr\.?|may|jun\.?|jul\.?|aug\.?|sep\.?|janvier|f[ée]vrier|avril|juillet|septembre|octobre|novembre|d[ée]cembre|january|february|march|april|june|july|august|september|october|november|december|\d{1,2}/)"
DATE_RANGE = re.compile(
    rf"((?:{MONTH}\s*)?{YEAR}(?:\s*(?:-|–|—|à|au|to|/)\s*(?:(?:{MONTH}\s*)?{YEAR}|aujourd'hui|présent|present|en cours|now|today))?)",
    re.I,
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(\+?\d[\d .()-]{7,}\d)")
LINK = re.compile(r"((?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|[\w-]+\.(?:dev|io|me))/?[\w/.-]*)", re.I)
QUANTIFIED = re.compile(r"\d+\s*(%|personnes|élèves|étudiants|participants|€|euros|f ?cfa|xof|k\b|clients|membres|heures|projets|users|people|students|members|hours|bénéficiaires|villages|écoles)|\b\d{2,}\b", re.I)

# Thèmes de sélection : ce qu'un jury cherche, et comment le repérer dans un CV.
THEMES = {
    "leadership": {
        "label": "leadership",
        "scholarship": r"leader|leadership|responsabilit|initiative",
        "cv": r"président|presid|responsable|dirig|pilot|encadr|coordonn|fond|capitaine|délégué|\bled\b|lead|manag|organis|chef",
        "advice": "La bourse valorise le leadership : décrivez une situation où vous avez pris la tête d'un projet, d'une équipe ou d'une association, avec le nombre de personnes concernées.",
    },
    "communaute": {
        "label": "engagement pour la communauté",
        "scholarship": r"communaut|société civile|impact|social|community|volunt|bénévol|citoyen",
        "cv": r"bénévol|associat|volunt|communaut|\bong\b|\bngo\b|humanitaire|caritati|sensibilis|mentor|tutorat|soutien scolaire|club",
        "advice": "Le jury attend un engagement au service des autres : ajoutez une rubrique Engagement avec vos actions associatives ou bénévoles et ce qu'elles ont changé.",
    },
    "recherche": {
        "label": "expérience de recherche",
        "scholarship": r"recherche|research|doctor|phd|scientifi|laborato",
        "cv": r"recherche|research|mémoire|thèse|thesis|publication|laborato|article|enquête|survey",
        "advice": "Mettez en avant votre mémoire ou vos travaux de recherche : sujet, méthode, encadrant et résultat principal.",
    },
    "excellence": {
        "label": "excellence académique",
        "scholarship": r"excellen|mérite|merit|meilleur|outstanding|high.achiev|talent",
        "cv": r"mention|major de|prix|award|distinction|excellence|meilleur|rang|classement|top \d|gpa|/20|félicitations|honou?rs",
        "advice": "La bourse sélectionne sur le mérite : indiquez vos mentions, votre rang ou votre moyenne, et les prix obtenus.",
    },
    "retour": {
        "label": "projet d'impact dans votre pays",
        "scholarship": r"retour|return|home country|pays d'origine|développement|development|réintégr|contribu",
        "cv": r"retour|revenir|mon pays|return|home country|contribuer|développement local|impact",
        "advice": "Cette bourse finance des personnes qui reviendront agir dans leur pays : précisez dans votre profil ou votre CV le problème concret que vous voulez traiter à votre retour.",
    },
    "innovation": {
        "label": "innovation et entrepreneuriat",
        "scholarship": r"innov|entrepren|startup|start-up|créati",
        "cv": r"start-?up|entrepren|créé|fondé|innov|prototype|hackathon|application|founded|built",
        "advice": "Le programme cherche des profils qui créent : citez un projet que vous avez lancé, un prototype ou une participation à un concours d'innovation.",
    },
    "international": {
        "label": "ouverture internationale",
        "scholarship": r"international|mobilit|intercultur|global|exchange|échange",
        "cv": r"international|échange|exchange|erasmus|mobilit|séjour|étranger|abroad|multiculturel|bilingue",
        "advice": "Montrez votre ouverture internationale : séjour à l'étranger, projet avec des partenaires d'autres pays, langues pratiquées.",
    },
}

THEMES_EN = {
    "leadership": ("leadership", "The scholarship values leadership: describe a time you led a project, a team or an association, with the number of people involved."),
    "communaute": ("community engagement", "The panel expects service to others: add a Community engagement section with your volunteer or association work and what it changed."),
    "recherche": ("research experience", "Highlight your thesis or research work: topic, method, supervisor and main result."),
    "excellence": ("academic excellence", "The scholarship selects on merit: state your honours, your class rank or average, and any awards."),
    "retour": ("impact project in your home country", "This scholarship funds people who will return to make a difference at home: state in your profile or CV the concrete problem you want to tackle when you return."),
    "innovation": ("innovation and entrepreneurship", "The programme looks for builders: mention a project you launched, a prototype or an innovation contest you entered."),
    "international": ("international outlook", "Show your international outlook: time abroad, projects with partners from other countries, languages you speak."),
}


def theme_label(k: str) -> str:
    return THEMES_EN[k][0] if is_en() and k in THEMES_EN else THEMES[k]["label"]


def theme_advice(k: str) -> str:
    return THEMES_EN[k][1] if is_en() and k in THEMES_EN else THEMES[k]["advice"]


CRITERIA_EN = {
    "coordonnees": "Contact details", "structure": "Structure and sections", "chronologie": "Dates and chronology",
    "verbes_action": "Action verbs", "resultats": "Measurable results", "longueur": "Appropriate length",
    "langues": "Languages and levels", "lisibilite": "Readability and style", "adequation": "Fit with the scholarship",
}

CRITERIA = [
    ("coordonnees", "Coordonnées", 8),
    ("structure", "Structure et rubriques", 12),
    ("chronologie", "Dates et chronologie", 10),
    ("verbes_action", "Verbes d'action", 10),
    ("resultats", "Résultats mesurables", 14),
    ("longueur", "Longueur adaptée", 8),
    ("langues", "Langues et niveaux", 10),
    ("lisibilite", "Lisibilité et style", 10),
    ("adequation", "Adéquation avec la bourse", 18),
]


# ------------------------------------------------------------------ outils
def _clean_line(line: str) -> str:
    return line.strip().strip("•●▪■◦○*·-–—>").strip()


def _starts_with_verb(line: str) -> bool:
    low = line.lower()
    return any(re.match(rf"{re.escape(v)}\b", low) for v in ACTION_VERBS)


def _years(text: str) -> list[int]:
    return [int(y) for y in re.findall(rf"\b({YEAR})\b", text)]


def _profile_text(p: Profile | None) -> str:
    if p is None:
        return ""
    return " ".join(filter(None, [p.experiences, p.engagement, p.project]))


def scholarship_text(s: Scholarship | None) -> str:
    if s is None:
        return ""
    return " ".join(filter(None, [s.title, s.organization, s.summary, " ".join(s.eligibility or []), " ".join(s.target_groups or [])]))


def detect_themes(s: Scholarship | None) -> list[str]:
    text = scholarship_text(s).lower()
    return [k for k, t in THEMES.items() if re.search(t["scholarship"], text)]


def theme_coverage(s: Scholarship | None, cv_text: str, p: Profile | None) -> tuple[list[str], list[str]]:
    """(thèmes couverts, thèmes manquants) parmi ceux que la bourse met en avant."""
    hay = f"{cv_text} {_profile_text(p)}".lower()
    covered, missing = [], []
    for k in detect_themes(s):
        (covered if re.search(THEMES[k]["cv"], hay) else missing).append(k)
    return covered, missing


# ------------------------------------------------------------------ diagnostic
def _status(score: int) -> str:
    return "ok" if score >= 75 else ("a_ameliorer" if score >= 45 else "manquant")


def diagnose_rules(text: str, p: Profile | None, s: Scholarship | None, email: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    sections = split_sections(text)
    lines = [_clean_line(l) for l in text.splitlines() if _clean_line(l)]
    words = writing.word_count(text)
    crit: dict[str, dict] = {}

    def put(key: str, score: int, finding: str, advice: str | None):
        crit[key] = {"score": max(0, min(100, int(score))), "finding": finding, "recommendation": advice}

    # 1. Coordonnées
    head = sections.get("entete", "") + "\n" + "\n".join(lines[:8])
    has_mail = bool(EMAIL.search(head)) or bool(email)
    has_phone = bool(PHONE.search(head)) or bool(p and p.phone)
    has_city = bool(p and (p.city or p.residence_country)) or bool(re.search(r"\b(lomé|dakar|abidjan|douala|yaoundé|cotonou|ouagadougou|bamako|niamey|accra|lagos|paris|lyon|rabat|tunis|kinshasa|libreville|conakry)\b", head, re.I))
    missing = [x for x, ok in ((t("e-mail", "email"), has_mail), (t("téléphone", "phone"), has_phone), (t("ville", "city"), has_city)) if not ok]
    if missing:
        put("coordonnees", 100 - 30 * len(missing), t(f"Il manque : {', '.join(missing)}.", f"Missing: {', '.join(missing)}."),
            t("Placez en haut du CV votre nom, votre e-mail, votre téléphone avec l'indicatif du pays et votre ville. Ces informations reprennent celles de votre profil.",
              "Put your name, email, phone number with country code and city at the top of the CV. These come from your profile."))
    else:
        put("coordonnees", 100, t("Nom, e-mail, téléphone et ville sont présents.", "Name, email, phone and city are present."), None)

    # 2. Structure
    need = [("formation", t("Formation", "Education")), ("experiences", t("Expériences", "Experience")), ("competences", t("Compétences", "Skills")), ("langues", t("Langues", "Languages"))]
    absent = [label for key, label in need if key not in sections]
    if absent:
        put("structure", 100 - 22 * len(absent), t(f"Rubriques introuvables : {', '.join(absent)}.", f"Sections not found: {', '.join(absent)}."),
            t("Donnez à chaque rubrique un titre clair sur sa propre ligne (Formation, Expériences, Compétences, Langues) : les jurys et les logiciels de tri lisent d'abord ces titres.",
              "Give each section a clear heading on its own line (Education, Experience, Skills, Languages). Panels and screening software read these headings first."))
    else:
        put("structure", 100, t("Les quatre rubriques attendues sont présentes.", "The four expected sections are present."), None)

    # 3. Dates et chronologie
    years = _years(text)
    future = sorted({y for y in years if y > today.year + 1})
    dated_blocks = [k for k in ("formation", "experiences") if k in sections]
    undated = [k for k in dated_blocks if not _years(sections[k])]
    chrono = 100
    notes = []
    if not years:
        chrono = 30
        notes.append(t("aucune date n'apparaît", "no dates appear"))
    if future:
        chrono -= 35
        notes.append(t(f"date(s) dans le futur : {', '.join(map(str, future))}", f"date(s) in the future: {', '.join(map(str, future))}"))
    if undated:
        chrono -= 25
        notes.append(t("une rubrique n'est pas datée", "a section has no dates"))
    for k in dated_blocks:
        ys = [max(_years(l)) for l in sections[k].splitlines() if _years(l)]
        if len(ys) >= 2 and ys[0] < ys[-1]:
            chrono -= 15
            notes.append(t("l'ordre n'est pas du plus récent au plus ancien", "entries are not in reverse chronological order"))
            break
    put("chronologie", chrono, (t("Dates complètes et bien ordonnées.", "Dates are complete and well ordered.") if not notes else t("Points relevés : ", "Issues found: ") + t(" ; ", "; ").join(notes) + "."),
        None if chrono >= 75 else t("Indiquez le mois et l'année de début et de fin de chaque étape, et classez-les du plus récent au plus ancien.",
                                    "Give the start and end month and year of each entry, and list them from most recent to oldest."))

    # 4. Verbes d'action
    exp_keys = ("experiences", "projets", "engagement", "recherche")
    exp_lines = [_clean_line(l) for k in exp_keys for l in sections.get(k, "").splitlines() if len(l.split()) >= 4]
    with_verbs = [l for l in exp_lines if _starts_with_verb(l)]
    verbs = int(100 * len(with_verbs) / len(exp_lines)) if exp_lines else 20
    verbs = min(100, int(verbs * 1.6)) if exp_lines else verbs
    put("verbes_action", verbs,
        (t(f"{len(with_verbs)} ligne(s) sur {len(exp_lines)} commencent par un verbe d'action.", f"{len(with_verbs)} of {len(exp_lines)} lines start with an action verb.") if exp_lines
         else t("Aucune ligne d'expérience détaillée.", "No detailed experience lines.")),
        None if verbs >= 75 else t("Commencez chaque ligne d'expérience par un verbe qui décrit votre action (organisé, conçu, encadré, analysé) plutôt que par un nom comme « gestion de » ou « participation à ».",
                                   "Start each experience line with a verb that describes what you did (organised, designed, supervised, analysed) rather than a noun such as \"management of\" or \"participation in\"."))

    # 5. Résultats mesurables
    quantified = [l for l in exp_lines if QUANTIFIED.search(l)]
    results = int(100 * len(quantified) / len(exp_lines)) if exp_lines else 10
    results = min(100, int(results * 2)) if exp_lines else results
    put("resultats", results,
        (t(f"{len(quantified)} ligne(s) sur {len(exp_lines)} donnent un chiffre ou un résultat.", f"{len(quantified)} of {len(exp_lines)} lines give a figure or a result.") if exp_lines
         else t("Aucun résultat chiffré.", "No quantified results.")),
        None if results >= 75 else t("Pour chaque expérience, précisez l'ampleur ou le résultat : nombre de personnes touchées, budget géré, délai tenu, note obtenue. Seuls des chiffres réels doivent apparaître.",
                                     "For each experience, state the scale or the result: people reached, budget managed, deadline met, grade obtained. Use real figures only."))

    # 6. Longueur
    doctoral = bool(p and p.target_level == "BAC7")
    low_limit, high_limit = (250, 1400) if doctoral else (220, 750)
    if words < low_limit:
        length = 45 if words < 120 else 65
        put("longueur", length, t(f"Votre CV compte {words} mots, c'est trop court pour convaincre un jury.", f"Your CV has {words} words, which is too short to convince a panel."),
            t("Détaillez deux ou trois réalisations par expérience et ajoutez vos projets, engagements et compétences techniques.",
              "Describe two or three achievements per experience and add your projects, commitments and technical skills."))
    elif words > high_limit:
        put("longueur", 60, t(f"Votre CV compte {words} mots, il dépassera la longueur attendue.", f"Your CV has {words} words and will exceed the expected length."),
            t("Gardez les expériences liées à votre projet d'études et regroupez les autres en une ligne. Visez une page, deux au maximum.",
              "Keep the experience related to your study plan and group the rest on one line. Aim for one page, two at most."))
    else:
        put("longueur", 100, t(f"{words} mots : longueur adaptée à votre niveau.", f"{words} words, a suitable length for your level."), None)

    # 7. Langues
    lang_text = sections.get("langues", "")
    has_levels = bool(re.search(r"\b(A1|A2|B1|B2|C1|C2|ielts|toefl|delf|dalf|tcf|testdaf|goethe|hsk|natif|maternelle|native|courant|fluent|bilingue)\b", lang_text, re.I))
    profile_scores = bool(p and p.language_scores)
    if not lang_text:
        put("langues", 30, t("Aucune rubrique Langues.", "No Languages section."),
            t("Ajoutez vos langues avec un niveau du Cadre européen (A1 à C2) ou votre score de test (IELTS, TOEFL, DELF).", "Add your languages with a CEFR level (A1 to C2) or your test score (IELTS, TOEFL, DELF)."))
    elif not has_levels:
        put("langues", 60, t("Les langues sont citées sans niveau.", "Languages are listed without a level."),
            t("Précisez un niveau pour chaque langue (B2, C1, langue maternelle) et le score de vos tests officiels.", "Give a level for each language (B2, C1, native) and your official test scores."))
    else:
        put("langues", 100 if (profile_scores or re.search(r"ielts|toefl|delf|dalf|tcf|testdaf|hsk", lang_text, re.I)) else 85,
            t("Langues indiquées avec leur niveau.", "Languages are listed with their level."), None)
    if s and s.language_tests and not re.search("|".join(map(re.escape, s.language_tests.keys())), text, re.I) and not profile_scores:
        crit["langues"]["score"] = min(crit["langues"]["score"], 55)
        tests = t(" ou ", " or ").join(f"{name} {m:g}" for name, m in s.language_tests.items())
        crit["langues"]["recommendation"] = t(f"La bourse demande un test de langue ({tests}) : indiquez votre score dans le CV et dans votre profil.",
                                              f"The scholarship requires a language test ({tests}): add your score to your CV and your profile.")

    # 8. Lisibilité
    long_lines = [l for l in lines if len(l.split()) > 32]
    first_person = [l for l in lines if re.match(r"^(je|j'|i)\b", l.lower())]
    readability = 100 - 12 * len(long_lines) - 6 * len(first_person)
    findings = []
    if long_lines:
        findings.append(t(f"{len(long_lines)} ligne(s) trop longue(s)", f"{len(long_lines)} line(s) too long"))
    if first_person:
        findings.append(t(f"{len(first_person)} ligne(s) écrite(s) à la première personne", f"{len(first_person)} line(s) written in the first person"))
    put("lisibilite", max(35, readability), (t("Lignes courtes et style direct.", "Short lines and a direct style.") if not findings else t(" ; ", "; ").join(findings).capitalize() + "."),
        None if readability >= 75 else t("Une idée par ligne, quinze à vingt-cinq mots au plus, sans « je » : le CV se lit en diagonale.",
                                         "One idea per line, fifteen to twenty-five words at most, without \"I\". A CV is skimmed, not read."))

    # 9. Adéquation avec la bourse
    if s:
        covered, missing_themes = theme_coverage(s, text, p)
        dom_ok = True
        if s.domains and "tous" not in s.domains and p and p.domain and p.domain not in s.domains:
            dom_ok = False
        base_score = 70 if not (covered or missing_themes) else int(100 * len(covered) / (len(covered) + len(missing_themes)))
        if not dom_ok:
            base_score = min(base_score, 40)
        labels_ok = ", ".join(theme_label(k) for k in covered)
        labels_ko = ", ".join(theme_label(k) for k in missing_themes)
        finding = []
        if covered:
            finding.append(t(f"Votre CV montre déjà : {labels_ok}", f"Your CV already shows {labels_ok}"))
        if missing_themes:
            finding.append(t(f"La bourse valorise aussi : {labels_ko}", f"The scholarship also values {labels_ko}"))
        if not dom_ok:
            finding.append(t("Votre domaine n'apparaît pas parmi ceux financés", "Your field is not among those funded"))
        advice = theme_advice(missing_themes[0]) if missing_themes else (None if dom_ok else t("Vérifiez que votre domaine d'études figure dans la liste des domaines financés avant de postuler.", "Check that your field of study is on the list of funded fields before applying."))
        put("adequation", base_score, (". ".join(finding) + ".") if finding else t("Aucun critère particulier relevé dans la description de la bourse.", "No specific criteria found in the scholarship description."), advice)
    else:
        domain_words = DOMAINS.get(p.domain or "", "") if p else ""
        ok = bool(domain_words) and any(w[:6].lower() in text.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{5,}", domain_words))
        put("adequation", 80 if ok else 60, t("Choisissez une bourse pour mesurer l'adéquation précise de votre CV.", "Choose a scholarship to measure exactly how well your CV fits.") if not ok else t("Votre CV parle bien de votre domaine d'études.", "Your CV clearly covers your field of study."),
            t("Sélectionnez la bourse visée : le diagnostic vérifiera les critères que son jury met en avant.", "Select the scholarship you are aiming for and the diagnostic will check the criteria its panel highlights."))

    criteria = [{"key": k, "label": t(label, CRITERIA_EN[k]), "weight": w, **crit[k], "status": _status(crit[k]["score"])} for k, label, w in CRITERIA]
    total = sum(c["score"] * c["weight"] for c in criteria) / sum(c["weight"] for c in criteria)
    rewrites = propose_rewrites(lines)
    priorities = [c["recommendation"] for c in sorted(criteria, key=lambda c: c["score"] * (1 + c["weight"] / 100)) if c["recommendation"]][:3]
    return {
        "score": int(round(total)),
        "verdict": verdict(int(round(total))),
        "criteria": criteria,
        "priorities": priorities,
        "rewrites": rewrites,
        "spelling": [],
        "sections_found": [SECTION_KEYS.get(k, k) for k in sections if k != "entete"],
        "word_count": words,
        "ai_used": False,
    }


def verdict(score: int) -> str:
    if score >= 80:
        return t("Votre CV est solide. Quelques ajustements le rendront prêt pour la bourse visée.", "Your CV is solid. A few adjustments will make it ready for this scholarship.")
    if score >= 60:
        return t("Une bonne base. Les recommandations ci-dessous feront la différence face au jury.", "A good base. The recommendations below will make the difference with the panel.")
    return t("Votre CV doit être renforcé avant l'envoi. Commencez par les trois priorités.", "Your CV needs strengthening before you send it. Start with the three priorities.")


def propose_rewrites(lines: list[str]) -> list[dict]:
    out = []
    for l in lines:
        proposal = apply_weak_start(l)
        if not proposal:
            continue
        why = t("Un verbe d'action en tête montre ce que vous avez fait vous-même.", "Starting with an action verb shows what you did yourself.")
        if not re.search(r"\d", l):
            why += t(" Ajoutez si possible un chiffre réel : combien de personnes, quel résultat.", " If you can, add a real figure: how many people, what result.")
        out.append({"original": l, "proposal": proposal, "why": why})
        if len(out) >= 8:
            break
    return out


DIAG_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": [k for k, _, _ in CRITERIA]},
                    "score": {"type": "integer"},
                    "finding": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["key", "score", "finding", "recommendation"],
                "additionalProperties": False,
            },
        },
        "rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"original": {"type": "string"}, "proposal": {"type": "string"}, "why": {"type": "string"}},
                "required": ["original", "proposal", "why"],
                "additionalProperties": False,
            },
        },
        "spelling": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["criteria", "rewrites", "spelling"],
    "additionalProperties": False,
}

DIAG_SYSTEM = """Vous êtes conseiller senior en candidatures de bourses d'études internationales. Vous relisez le CV
d'un étudiant et vous rendez un diagnostic précis, en français, en vouvoyant l'étudiant.

Critères (clé, ce que vous évaluez) :
- verbes_action : chaque ligne d'expérience commence-t-elle par un verbe d'action précis ?
- resultats : les expériences donnent-elles des résultats mesurables réels ?
- lisibilite : lignes courtes, style direct, pas de « je », mise en forme homogène ;
- adequation : le CV répond-il aux critères de la bourse visée (thèmes, domaine, niveau) ?
- structure, chronologie, coordonnees, longueur, langues : vous pouvez préciser le constat.

Pour chaque critère : une note de 0 à 100, un constat factuel qui cite le CV, une recommandation concrète
et applicable (une ou deux phrases). Si le critère est satisfait, recommandation vide.
Réécritures : jusqu'à 8 lignes du CV, recopiées exactement dans « original », avec une meilleure version.
N'ajoutez aucun fait, chiffre, diplôme ou nom absent du CV. Si un chiffre manque, dites-le dans « why ».
Orthographe : listez les fautes trouvées sous la forme « mot fautif → correction ».
Style : phrases complètes, pas de tiret cadratin, pas de formule creuse."""


def diagnose(text: str, p: Profile | None, s: Scholarship | None, use_ai: bool, email: str | None = None) -> dict:
    base = diagnose_rules(text, p, s, email=email)
    if not use_ai:
        return base
    focus = f"\n\nBOURSE VISÉE\n{s.title} ({s.organization})\n{s.summary}\nConditions : {'; '.join(s.eligibility or [])}" if s else ""
    rules_view = "\n".join(f"- {c['key']} : {c['score']} ({c['finding']})" for c in base["criteria"])
    user = f"Pré-analyse automatique :\n{rules_view}{focus}\n\nCV :\n{text[:15000]}"
    system = DIAG_SYSTEM + ("\n\nRédigez les constats, recommandations et explications en anglais (l'étudiant utilise le site en anglais)." if is_en() else "")
    data = ask_json(system, user, DIAG_SCHEMA, effort="medium", max_tokens=8000, cache=True)
    if not data:
        return base
    objective = {"coordonnees", "longueur", "chronologie"}
    by_key = {c["key"]: c for c in data.get("criteria", [])}
    for c in base["criteria"]:
        ai = by_key.get(c["key"])
        if not ai:
            continue
        if c["key"] not in objective:
            c["score"] = max(0, min(100, int(ai["score"])))
        c["finding"] = writing.clean_punctuation(ai["finding"]) or c["finding"]
        c["recommendation"] = writing.clean_punctuation(ai["recommendation"]) or (None if c["score"] >= 75 else c["recommendation"])
        c["status"] = _status(c["score"])
    total = sum(c["score"] * c["weight"] for c in base["criteria"]) / sum(c["weight"] for c in base["criteria"])
    base["score"] = int(round(total))
    base["verdict"] = verdict(base["score"])
    base["priorities"] = [c["recommendation"] for c in sorted(base["criteria"], key=lambda c: c["score"]) if c["recommendation"]][:3]
    rw = [r for r in data.get("rewrites", []) if r.get("original") and r.get("proposal")]
    if rw:
        base["rewrites"] = [{k: writing.clean_punctuation(v) for k, v in r.items()} for r in rw[:8]]
    base["spelling"] = [writing.clean_punctuation(x) for x in data.get("spelling", [])][:15]
    base["ai_used"] = True
    return base


# ------------------------------------------------------------------ CV structuré
def _parse_entries(block: str) -> list[dict]:
    entries: list[dict] = []
    for raw in block.splitlines():
        bullet = bool(re.match(r"^\s*[•●▪■◦○*·\-–—>]", raw))
        line = _clean_line(raw)
        if not line:
            continue
        dates_match = DATE_RANGE.search(line)
        starts_entry = (dates_match is not None and not bullet) or (not entries) or (not bullet and not _starts_with_verb(line) and len(line.split()) <= 12 and not entries[-1]["bullets"] and entries[-1]["title"] == "")
        if dates_match and not bullet:
            dates = dates_match.group(1)
            rest = (line[: dates_match.start()] + " " + line[dates_match.end():]).strip(" ,:;|-–—")
            title, org = rest, ""
            for sep in (" | ", " - ", " – ", ", ", " chez ", " at ", " à l'", " au ", " à "):
                if sep in rest:
                    a, b = rest.split(sep, 1)
                    if a.strip() and b.strip():
                        title, org = a.strip(), (b.strip() if sep not in (" à l'",) else "l'" + b.strip())
                        break
            entries.append({"title": title, "organization": org, "location": "", "dates": _normalize_dates(dates), "bullets": []})
        elif starts_entry and not entries:
            entries.append({"title": line, "organization": "", "location": "", "dates": "", "bullets": []})
        elif entries and not entries[-1]["organization"] and not entries[-1]["bullets"] and not bullet and not _starts_with_verb(line) and len(line.split()) <= 8:
            entries[-1]["organization"] = line
        else:
            entries[-1]["bullets"].append(line)
    return entries


def _normalize_dates(d: str) -> str:
    d = re.sub(r"\s*(?:–|—|-|/(?=\s*\d{4})|\bà\b|\bau\b|\bto\b)\s*", " - ", d.strip(), count=1)
    d = re.sub(r"\s{2,}", " ", d)
    return d[:1].upper() + d[1:]


def _improve_bullet(line: str) -> str:
    out = apply_weak_start(line.strip()) or line.strip()
    out = writing.clean_punctuation(out).rstrip(".;")
    return out[:1].upper() + out[1:] if out else out


def _max_year(e: dict) -> int:
    ys = _years(e.get("dates", "")) or _years(e.get("title", ""))
    if re.search(r"aujourd|présent|present|en cours|now|today", e.get("dates", ""), re.I):
        return 9999
    return max(ys) if ys else 0


def _list_items(block: str) -> list[str]:
    items = []
    for raw in block.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        items.append(writing.clean_punctuation(line).rstrip("."))
    return items


def _languages_items(block: str, p: Profile | None, language: str) -> list[str]:
    items = _list_items(block) if block else []
    if p and p.languages and not items:
        names = LANG_NAMES["en" if language == "en" else "fr"]
        words = LEVEL_WORDS["en" if language == "en" else "fr"]
        for code, level in p.languages.items():
            name = names.get(code, code.upper())
            lvl = words.get(str(level).lower(), str(level))
            items.append(f"{name}, {lvl}")
    if p and p.language_scores:
        scores = ", ".join(f"{t} {v:g}" for t, v in p.language_scores.items())
        if not any(t.lower() in " ".join(items).lower() for t in p.language_scores):
            items.append(scores)
    return items


def header_from(p: Profile | None, cv_text: str, email: str | None, fmt: CVFormat, language: str, s: Scholarship | None) -> dict:
    first_lines = [l.strip() for l in cv_text.splitlines()[:6] if l.strip()]
    name = (p.full_name if p and p.full_name else (first_lines[0] if first_lines and len(first_lines[0].split()) <= 5 and not EMAIL.search(first_lines[0]) else "")) or ""
    mail = email or (EMAIL.search(cv_text).group(0) if EMAIL.search(cv_text) else "")
    phone = (p.phone if p and p.phone else (PHONE.search("\n".join(first_lines)).group(1).strip() if PHONE.search("\n".join(first_lines)) else "")) or ""
    country = country_name(p.residence_country, language) if p and p.residence_country else ""
    location = ", ".join(x for x in [p.city if p else None, country] if x)
    links = (p.links if p and p.links else ", ".join(dict.fromkeys(m.group(1) for m in LINK.finditer(cv_text)))) or ""
    level = LEVEL_NOUN["en" if language == "en" else "fr"].get(p.target_level or "", "") if p else ""
    domain = domain_name(p.domain, language) if p and p.domain and p.domain != "tous" else ""
    if language == "en":
        headline = f"{level} applicant in {domain.lower() if domain else ''}".strip() if level else domain
        headline = headline.replace(" in ", " in ", 1) if domain else (f"{level} applicant" if level else "")
    else:
        headline = f"Projet de {level.lower()} en {domain.lower()}" if level and domain else (f"Projet de {level.lower()}" if level else domain)
    out = {"name": name, "headline": headline, "email": mail, "phone": phone, "location": location, "links": links, "birth_date": "", "nationality": ""}
    if fmt.show_birth_date and p and p.birth_date:
        b = p.birth_date
        out["birth_date"] = f"{b.day} {EN_MONTHS[b.month - 1]} {b.year}" if language == "en" else b.strftime("%d/%m/%Y")
    if fmt.show_nationality and p and p.nationalities:
        out["nationality"] = ", ".join(country_name(c, language) for c in p.nationalities)
    return out


def _signature(fmt: CVFormat, p: Profile | None, language: str, today: date) -> str:
    if not fmt.signature:
        return ""
    place = p.city if p and p.city else ""
    stamp = today.strftime("%d.%m.%Y")
    return f"{place}, {stamp}" if place else stamp


def build_cv_rules(cv_text: str, p: Profile | None, s: Scholarship | None, email: str | None, today: date | None = None) -> dict:
    today = today or date.today()
    fmt, reason = choose_format(s, p)
    language = document_language(s, p)
    raw = split_sections(cv_text)
    changes: list[str] = []
    sections_by_key: dict[str, dict] = {}

    for fr_key, block in raw.items():
        if fr_key in ("entete",):
            continue
        key = SECTION_KEYS.get(fr_key, fr_key)
        if key == "summary":
            continue
        if key in ("skills", "languages", "interests", "references", "awards", "publications"):
            items = _languages_items(block, p, language) if key == "languages" else _list_items(block)
            sections_by_key[key] = {"key": key, "title": "", "kind": "list", "entries": [], "items": items}
        else:
            entries = _parse_entries(block)
            improved = 0
            for e in entries:
                new = [_improve_bullet(b) for b in e["bullets"]]
                improved += sum(1 for a, b in zip(e["bullets"], new) if a.rstrip(".") != b)
                e["bullets"] = [b for b in new if b]
                e["title"] = writing.clean_punctuation(e["title"]).rstrip(".")
                e["organization"] = writing.clean_punctuation(e["organization"]).rstrip(".")
            before = [id(e) for e in entries]
            entries.sort(key=_max_year, reverse=True)
            if [id(e) for e in entries] != before:
                changes.append(t(f"{section_title(fmt, key, 'fr')} : étapes reclassées de la plus récente à la plus ancienne.", f"{section_title(fmt, key, 'en')}: entries reordered from most recent to oldest."))
            if improved:
                changes.append(t(f"{section_title(fmt, key, 'fr')} : {improved} ligne(s) reformulée(s) avec un verbe d'action.", f"{section_title(fmt, key, 'en')}: {improved} line(s) rewritten with an action verb."))
            sections_by_key[key] = {"key": key, "title": "", "kind": "entries", "entries": entries, "items": []}

    if "languages" not in sections_by_key and p and (p.languages or p.language_scores):
        sections_by_key["languages"] = {"key": "languages", "title": "", "kind": "list", "entries": [], "items": _languages_items("", p, language)}
        changes.append(t("Rubrique Langues ajoutée à partir de votre profil.", "Languages section added from your profile."))
    if "engagement" not in sections_by_key and p and p.engagement:
        sections_by_key["engagement"] = {"key": "engagement", "title": "", "kind": "list", "entries": [], "items": _list_items(p.engagement)}
        changes.append(t("Rubrique Engagement ajoutée à partir de votre profil.", "Engagement section added from your profile."))

    # Ordre du format, puis les thèmes valorisés par la bourse remontent
    order = list(fmt.order) + [k for k in sections_by_key if k not in fmt.order]
    _, missing = theme_coverage(s, cv_text, p)
    if s and "engagement" in sections_by_key and ("communaute" in detect_themes(s) or "leadership" in detect_themes(s)):
        if "engagement" in order and order.index("engagement") > 2:
            order.remove("engagement")
            order.insert(2, "engagement")
            changes.append(t("Engagement placé juste après les expériences : la bourse valorise le leadership et l'engagement.", "Engagement moved right after experience, because the scholarship values leadership and engagement."))
    sections = []
    for key in order:
        sec = sections_by_key.get(key)
        if not sec or not (sec["entries"] or sec["items"]):
            continue
        sec["title"] = section_title(fmt, key, language)
        sections.append(sec)

    summary = ""
    if p and p.project:
        sents = writing.split_sentences(writing.clean_punctuation(p.project))
        summary = " ".join(writing.complete_sentence(x) for x in sents[:2])
    elif raw.get("profil"):
        summary = " ".join(writing.complete_sentence(x) for x in writing.split_sentences(writing.clean_punctuation(raw["profil"].replace("\n", " ")))[:3])
    if summary:
        changes.append(t(f"{fmt.summary_title_fr} rédigé à partir de votre projet, en tête du CV.", f"{fmt.summary_title_en} written from your study plan, at the top of the CV."))
    changes.insert(0, t(f"Format appliqué : {fmt.label}.", f"Format applied: {fmt.label_en}."))

    return {
        "language": language,
        "format": fmt.code,
        "format_label": fmt.label_en if language == "en" else fmt.label,
        "format_reason": reason,
        "format_rules": list(fmt.rules),
        "layout": fmt.layout,
        "header": header_from(p, cv_text, email, fmt, language, s),
        "summary_title": fmt.summary_title_en if language == "en" else fmt.summary_title_fr,
        "summary": summary,
        "sections": sections,
        "signature": _signature(fmt, p, language, today),
        "changes": changes,
        "scholarship_id": s.id if s else None,
        "scholarship_title": s.title if s else None,
        "ai_used": False,
    }


CV_BUILD_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": ["education", "experience", "projects", "skills", "languages", "engagement", "interests", "research", "publications", "references", "awards"]},
                    "kind": {"type": "string", "enum": ["entries", "list"]},
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"}, "organization": {"type": "string"}, "location": {"type": "string"},
                                "dates": {"type": "string"}, "bullets": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["title", "organization", "location", "dates", "bullets"],
                            "additionalProperties": False,
                        },
                    },
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["key", "kind", "entries", "items"],
                "additionalProperties": False,
            },
        },
        "changes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "summary", "sections", "changes"],
    "additionalProperties": False,
}

CV_BUILD_SYSTEM = """Vous êtes rédacteur de CV pour des candidatures de bourses d'études internationales. Vous produisez
la version finale du CV d'un étudiant, prête à être envoyée, au format exigé et dans la langue demandée.

Règles de fond :
- Utilisez uniquement les faits du CV d'origine et du profil. Aucune expérience, date, note, chiffre,
  employeur ou distinction ne doit être ajouté. Si un chiffre manque, formulez la ligne sans chiffre.
- Adaptez au jury de la bourse : placez d'abord ce qui répond à ses critères, reprenez ses mots-clés
  lorsqu'ils décrivent réellement l'expérience, retirez ce qui n'apporte rien à cette candidature.
- Chaque ligne d'expérience commence par un verbe d'action au passé (en français : participe passé sans
  « j'ai », ex. « Organisé », « Conçu » ; en anglais : « Led », « Designed »). Deux à quatre lignes par étape.
- Dates homogènes, du plus récent au plus ancien (« sept. 2022 - juin 2024 », « 2022 - 2024 »).
- Traduisez fidèlement si la langue demandée diffère de celle du CV d'origine.

Règles de forme :
- Pas de tiret cadratin ni demi-cadratin comme ponctuation, pas de point-virgule en fin de ligne,
  pas de point final sur les lignes d'expérience, pas de crochets ni d'emplacement à compléter.
- Aucune formule creuse (« passionné », « dynamique et motivé », « force de proposition », « team player »).
- Le résumé (summary) tient en deux ou trois phrases complètes, précises, sans « je » en anglais
  (style CV) et sans adjectifs vides. Il annonce le projet d'études et ce qui le rend crédible.
- headline : une ligne courte qui annonce le diplôme visé et le domaine.
- changes : 3 à 6 phrases courtes en français, au vouvoiement, qui expliquent ce qui a été adapté et pourquoi."""


def build_cv(cv_text: str, p: Profile | None, s: Scholarship | None, email: str | None, use_ai: bool) -> dict:
    base = build_cv_rules(cv_text, p, s, email)
    if not use_ai:
        return base
    fmt_rules = "\n".join(f"- {r}" for r in base["format_rules"])
    sch = ""
    if s:
        sch = f"""BOURSE
Nom : {s.title}
Organisme : {s.organization}
Description : {s.summary}
Conditions : {'; '.join(s.eligibility or [])}
Thèmes valorisés : {', '.join(THEMES[k]['label'] for k in detect_themes(s)) or 'non précisés'}
"""
    prof = ""
    if p:
        prof = f"""PROFIL
Domaine : {DOMAINS.get(p.domain or '', '?')} ; établissement : {p.institution or '?'} ; moyenne : {p.grade_average if p.grade_average is not None else '?'}/20
Langues : {p.languages} ; tests : {p.language_scores}
Expériences (profil) : {p.experiences or '-'}
Engagement (profil) : {p.engagement or '-'}
Projet : {p.project or '-'}
"""
    user = f"""Langue du CV : {'anglais' if base['language'] == 'en' else 'français'}
Format : {base['format_label']}
Règles du format :
{fmt_rules}
Ordre des rubriques conseillé : {', '.join(s_['key'] for s_ in base['sections'])}

{sch}
{prof}
CV D'ORIGINE
{cv_text[:14000]}"""
    data = ask_json(CV_BUILD_SYSTEM, user, CV_BUILD_SCHEMA, effort="high", max_tokens=12000)
    if not data or not data.get("sections"):
        return base
    fmt = next((f for f in [choose_format(s, p)[0]]), None)
    lang = base["language"]
    sections = []
    for sec in data["sections"]:
        entries = []
        for e in sec.get("entries", []):
            bullets = [writing.clean_punctuation(b, lang).rstrip(".;") for b in e.get("bullets", []) if b and "[" not in b]
            entries.append({k: writing.clean_punctuation(e.get(k, ""), lang).rstrip(".") for k in ("title", "organization", "location", "dates")} | {"bullets": bullets})
        items = [writing.clean_punctuation(i, lang).rstrip(".") for i in sec.get("items", []) if i and "[" not in i]
        if not entries and not items:
            continue
        sections.append({"key": sec["key"], "title": section_title(fmt, sec["key"], lang), "kind": sec["kind"], "entries": entries, "items": items})
    base["sections"] = sections
    base["summary"] = " ".join(writing.complete_sentence(x) for x in writing.split_sentences(writing.clean_punctuation(data.get("summary", ""), lang)))
    if data.get("headline"):
        base["header"]["headline"] = writing.clean_punctuation(data["headline"], lang).rstrip(".")
    base["changes"] = [t(f"Format appliqué : {fmt.label}.", f"Format applied: {fmt.label_en}.")] + [writing.complete_sentence(writing.clean_punctuation(c)) for c in data.get("changes", [])][:6]
    base["ai_used"] = True
    return base


def cv_plain_text(cv: dict) -> str:
    """Version texte du CV structuré (enregistrée dans le profil pour le matching et les lettres)."""
    h = cv.get("header", {})
    out = [h.get("name", ""), h.get("headline", ""), " | ".join(x for x in [h.get("email"), h.get("phone"), h.get("location"), h.get("links")] if x), ""]
    if cv.get("summary"):
        out += [cv.get("summary_title", "Profil").upper(), cv["summary"], ""]
    for sec in cv.get("sections", []):
        out.append(sec["title"].upper())
        for e in sec.get("entries", []):
            out.append(" | ".join(x for x in [e.get("dates"), e.get("title"), e.get("organization"), e.get("location")] if x))
            out += [f"- {b}" for b in e.get("bullets", [])]
        out += sec.get("items", [])
        out.append("")
    return "\n".join(out).strip()
