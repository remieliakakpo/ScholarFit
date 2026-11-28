"""Style rédactionnel des CV et lettres ScholarFit (version sans IA et relecture après l'IA).

Choix validés avec la fondatrice (2026-11-27) :
- En français, les lignes d'expérience sont des tâches réalisées au style nominal, comme dans les CV
  français soignés : « Développement d'un tableau de bord… », « Formation de 15 agents… ». Jamais de
  participe passé seul en début de ligne (« Développé un tableau… »).
- En anglais, l'usage reste le verbe d'action au passé (« Built », « Trained »).
- Le profil est fait de vraies phrases, jamais de fragments (« Compétences clés en… »).
- Les compétences sont rangées par catégorie et triées selon la bourse.
"""
from __future__ import annotations

import re

# Verbe (infinitif et participe passé) → nom d'action. Le genre du nom sert à l'article.
NOMINAL_FR: dict[str, str] = {
    "développer": "Développement", "concevoir": "Conception", "créer": "Création", "former": "Formation",
    "organiser": "Organisation", "gérer": "Gestion", "analyser": "Analyse", "réaliser": "Réalisation",
    "mettre en place": "Mise en place", "mettre en œuvre": "Mise en œuvre", "encadrer": "Encadrement",
    "coordonner": "Coordination", "animer": "Animation", "rédiger": "Rédaction", "participer": "Participation",
    "accompagner": "Accompagnement", "superviser": "Supervision", "piloter": "Pilotage", "nettoyer": "Nettoyage",
    "déployer": "Déploiement", "automatiser": "Automatisation", "collecter": "Collecte", "traiter": "Traitement",
    "sensibiliser": "Sensibilisation", "conduire": "Conduite", "mener": "Conduite", "enseigner": "Enseignement",
    "suivre": "Suivi", "évaluer": "Évaluation", "élaborer": "Élaboration", "préparer": "Préparation",
    "présenter": "Présentation", "contribuer": "Contribution", "appuyer": "Appui", "assister": "Assistance",
    "installer": "Installation", "configurer": "Configuration", "maintenir": "Maintenance", "optimiser": "Optimisation",
    "planifier": "Planification", "produire": "Production", "publier": "Publication", "recruter": "Recrutement",
    "tester": "Tests", "modéliser": "Modélisation", "programmer": "Programmation", "construire": "Construction",
    "lancer": "Lancement", "améliorer": "Amélioration", "négocier": "Négociation", "fonder": "Création",
    "mobiliser": "Mobilisation", "représenter": "Représentation", "conseiller": "Conseil", "traduire": "Traduction",
    "étudier": "Étude", "réduire": "Réduction", "augmenter": "Augmentation", "intégrer": "Intégration",
    "documenter": "Documentation", "cartographier": "Cartographie", "superviser": "Supervision",
    "administrer": "Administration", "rénover": "Rénovation", "moderniser": "Modernisation", "vérifier": "Vérification",
    "contrôler": "Contrôle", "auditer": "Audit", "former à": "Formation",
}
PARTICIPLES_FR: dict[str, str] = {
    "développé": "développer", "conçu": "concevoir", "créé": "créer", "formé": "former", "organisé": "organiser",
    "géré": "gérer", "analysé": "analyser", "réalisé": "réaliser", "mis en place": "mettre en place",
    "mis en œuvre": "mettre en œuvre", "encadré": "encadrer", "coordonné": "coordonner", "animé": "animer",
    "rédigé": "rédiger", "participé": "participer", "accompagné": "accompagner", "supervisé": "superviser",
    "piloté": "piloter", "nettoyé": "nettoyer", "déployé": "déployer", "automatisé": "automatiser",
    "collecté": "collecter", "traité": "traiter", "sensibilisé": "sensibiliser", "conduit": "conduire",
    "mené": "mener", "enseigné": "enseigner", "suivi": "suivre", "évalué": "évaluer", "élaboré": "élaborer",
    "préparé": "préparer", "présenté": "présenter", "contribué": "contribuer", "appuyé": "appuyer",
    "assisté": "assister", "installé": "installer", "configuré": "configurer", "maintenu": "maintenir",
    "optimisé": "optimiser", "planifié": "planifier", "produit": "produire", "publié": "publier",
    "recruté": "recruter", "testé": "tester", "modélisé": "modéliser", "programmé": "programmer",
    "construit": "construire", "lancé": "lancer", "amélioré": "améliorer", "négocié": "négocier", "fondé": "fonder",
    "mobilisé": "mobiliser", "représenté": "représenter", "conseillé": "conseiller", "traduit": "traduire",
    "étudié": "étudier", "réduit": "réduire", "augmenté": "augmenter", "intégré": "intégrer",
    "documenté": "documenter", "administré": "administrer", "vérifié": "vérifier", "contrôlé": "contrôler",
}
# « Assuré la maintenance du parc » → « Maintenance du parc » : le verbe n'apporte rien
EMPTY_VERBS_FR = ("assuré", "effectué", "réalisé", "fait", "assurer", "effectuer", "réaliser", "faire", "pris en charge", "prendre en charge")
ACTION_NOUNS_FR = {v.lower() for v in NOMINAL_FR.values()} | {
    "maintenance", "gestion", "suivi", "veille", "support", "accueil", "saisie", "rédaction", "participation",
    "co-organisation", "co-animation", "co-rédaction", "tutorat", "mentorat", "recherche", "enquête", "interprétation",
}
VOWEL = "aeiouyhâàéèêëîïôöûùœAEIOUYHÂÀÉÈÊËÎÏÔÖÛÙŒ"


def _de(obj: str) -> str:
    """« de » + complément, avec contractions : de le → du, de les → des, de un → d'un, voyelle → d'."""
    o = obj.strip()
    low = o.lower()
    if low.startswith(("des ", "du ", "d'", "d’")):
        return o
    for a, b in (("le ", "du "), ("les ", "des ")):
        if low.startswith(a):
            return b + o[len(a):]
    if low.startswith(("à ", "au ", "aux ", "en ", "sur ", "avec ", "pour ", "dans ", "auprès ")):
        return o
    if low.startswith(("la ", "l'", "l’")):
        return "de " + o
    if o[:1] in VOWEL:
        return "d'" + o
    return "de " + o


_PHRASE_FIXES_FR = (
    (r"\bà la bureautique\b", "aux outils bureautiques"),
    (r"\ben bureautique\b", "aux outils bureautiques"),
    (r"\bà l'informatique\b", "aux outils informatiques"),
)


def to_nominal_fr(line: str) -> str:
    out = _to_nominal_fr(line)
    for pat, rep in _PHRASE_FIXES_FR:
        out = re.sub(pat, rep, out)
    return out


def _to_nominal_fr(line: str) -> str:
    """Ligne d'expérience au style nominal : « Développé un tableau de bord » → « Développement d'un tableau de bord »,
    « Formé 15 agents à la bureautique » → « Formation de 15 agents à la bureautique »,
    « Assuré la maintenance du parc » → « Maintenance du parc », « J'ai organisé un atelier » → « Organisation d'un atelier »."""
    s = re.sub(r"\s+", " ", line.strip()).rstrip(".;")
    s = re.sub(r"^(j'ai|j’ai|nous avons|ai)\s+", "", s, flags=re.I)
    s = re.sub(r"^(été\s+)?(responsable|en charge)\s+(de la|de l'|du|des|de|d')\s*",
               lambda m: "Pilotage " + {"de la": "de la ", "de l'": "de l'", "du": "du ", "des": "des ", "de": "de ", "d'": "d'"}[m.group(3).lower()],
               s, flags=re.I) if not re.match(r"^(été\s+)?(responsable|en charge)\s+(de|du|des|d')\s+(la |l')?(gestion|suivi|coordination|pilotage|organisation|maintenance|mise)\b", s, re.I) else \
        re.sub(r"^(été\s+)?(responsable|en charge)\s+(de la|de l'|du|des|de|d')\s*", "", s, flags=re.I)
    s = re.sub(r"^(été\s+)?charg[ée]e?s?\s+(de la|de l'|du|des|de|d')\s*", "", s, flags=re.I)
    s = re.sub(r"^aide\s+(à|a)\s+", "Appui à ", s, flags=re.I)
    s = re.sub(r"^travaill[ée]\s+(sur|dans)\s+", "Travail sur ", s, flags=re.I)
    s = s[:1].upper() + s[1:]
    low = s.lower()
    for v in EMPTY_VERBS_FR:
        if low.startswith(v + " "):
            rest = s[len(v) + 1:].strip()
            rest = re.sub(r"^(la|le|les|l'|l’|un|une|des)\s*", "", rest, flags=re.I) if not re.match(r"^l['’]", rest) else rest[2:]
            return rest[:1].upper() + rest[1:] if rest else s
    # participe passé ou infinitif en tête (le plus long d'abord : « mis en place » avant « mis »)
    candidates = sorted(list(PARTICIPLES_FR) + list(NOMINAL_FR), key=len, reverse=True)
    for c in candidates:
        if low.startswith(c + " ") or low == c:
            inf = PARTICIPLES_FR.get(c, c)
            noun = NOMINAL_FR.get(inf)
            if not noun:
                return s[:1].upper() + s[1:]
            rest = s[len(c):].strip()
            if not rest:
                return noun
            if re.match(r"^(à|a|au|aux)\s", rest, re.I) and noun in ("Participation", "Contribution"):
                rest = re.sub(r"^a\s", "à ", rest)
                return f"{noun} {rest}"
            return f"{noun} {_de(rest)}"
    return s[:1].upper() + s[1:]


def starts_with_action(line: str, language: str = "fr") -> bool:
    w = re.split(r"[\s']", line.strip().lower(), maxsplit=1)[0] if line.strip() else ""
    if language == "fr":
        return w in ACTION_NOUNS_FR or line.strip().lower().startswith(("mise en ", "prise en "))
    return False


# ------------------------------------------------------------------ établissements
FEM_ORGS = ("mairie", "université", "universite", "banque", "direction", "agence", "société", "societe", "fondation",
            "organisation", "commission", "chambre", "cour", "ambassade", "association", "école", "ecole", "faculté",
            "clinique", "préfecture", "prefecture", "communauté", "caisse", "compagnie", "coopérative", "cooperative",
            "radio", "télévision", "station", "plateforme", "start-up", "startup", "entreprise", "ong", "délégation", "mission")
MASC_ORGS = ("ministère", "ministere", "centre", "cabinet", "bureau", "conseil", "institut", "laboratoire", "lycée", "lycee",
             "collège", "college", "programme", "fonds", "groupe", "hôpital", "hopital", "service", "projet", "club",
             "réseau", "reseau", "port", "office", "secrétariat", "secretariat", "comité", "comite", "collectif", "parlement")


def at_org_fr(org: str) -> str:
    """« Mairie du Golfe 1 » → « à la Mairie du Golfe 1 » ; « Ministère… » → « au Ministère… » ;
    « Togo Data Lab, Lomé » → « chez Togo Data Lab, à Lomé »."""
    org = org.strip()
    city = ""
    m = re.match(r"^(.*?),\s*([A-ZÀ-Ý][\w'’ -]{1,30})$", org)
    if m and not re.search(r"\b(université|ministère|centre)\b", m.group(2), re.I):
        org, city = m.group(1).strip(), m.group(2).strip()
    first = org.split()[0].lower() if org else ""
    if re.match(r"^(la|le|les|l'|l’)\b", org, re.I):
        out = "à " + org[0].lower() + org[1:]
        out = re.sub(r"^à le ", "au ", out)
        out = re.sub(r"^à les ", "aux ", out)
    elif first in FEM_ORGS:
        out = ("à l'" if org[:1] in VOWEL else "à la ") + org
    elif first in MASC_ORGS:
        out = ("à l'" if org[:1] in VOWEL else "au ") + org
    else:
        out = "chez " + org
    return out + (f", à {city}" if city else "")


# ------------------------------------------------------------------ texte
def split_outside_parens(text: str, sep: str = ",") -> list[str]:
    """Découpe sur `sep` en ignorant ce qui est entre parenthèses : « App (Flutter, Firebase), 2 000 utilisateurs »."""
    out, buf, depth = [], [], 0
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf).strip())
    return [x for x in out if x]


def smart_lower(title: str) -> str:
    """« Licence en Informatique » → « licence en informatique », sans toucher aux sigles (MIAGE, BTS, IA)."""
    words = title.split(" ")
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"[^\wÀ-ÿ]", "", w)
        if core.isupper() and (len(core) >= 2 or i > 0):
            out.append(w)
        elif i > 0 and re.match(r"^[A-ZÀ-Ý][a-zà-ÿ]", w) and words[i - 1].lower() in ("de", "du", "d'université", "à", "of"):
            out.append(w)  # nom propre probable : « Université de Lomé »
        else:
            out.append(w[:1].lower() + w[1:] if i == 0 or not re.match(r"^[A-ZÀ-Ý][a-zà-ÿ]+$", w) else w.lower())
    return " ".join(out)


MENTION = re.compile(r",?\s*(?:avec\s+)?(?:la\s+)?mention\s+(très bien|tres bien|bien|assez bien|passable|honorable|très honorable|excellent)(\s*\([^)]*\))?", re.I)


def extract_mention(text: str) -> tuple[str, str]:
    """« Université de Lomé, mention Bien (14,8/20) » → (« Université de Lomé », « Mention Bien (14,8/20) »)."""
    m = MENTION.search(text or "")
    if not m:
        return text, ""
    rest = (text[: m.start()] + text[m.end():]).strip(" ,;")
    mention = "Mention " + m.group(1)[:1].upper() + m.group(1)[1:].lower() + (m.group(2) or "")
    return rest, mention


SINCE = re.compile(r",?\s*(?:depuis|since)\s+((?:[a-zéû]+\.?\s+)?(?:19|20)\d{2})\s*$", re.I)


def split_since(text: str) -> tuple[str, str]:
    """« Bénévole, club… depuis 2022 » → (« Bénévole, club… », « Depuis 2022 »)."""
    m = SINCE.search(text or "")
    if not m:
        return text, ""
    word = "Since" if m.group(0).strip(" ,").lower().startswith("since") else "Depuis"
    return text[: m.start()].strip(" ,"), f"{word} {m.group(1)}"


# ------------------------------------------------------------------ compétences par catégorie
SKILL_CATEGORIES: list[tuple[str, str, tuple[str, ...]]] = [
    ("Programmation", "Programming", ("python", "java", "javascript", "typescript", "c", "c++", "c#", "php", "r", "sql", "matlab",
                                       "kotlin", "swift", "go", "rust", "scala", "bash", "vba", "julia", "dart", "html", "css")),
    ("Développement web et mobile", "Web and mobile development", ("django", "flask", "fastapi", "react", "angular", "vue", "node",
                                       "node.js", "laravel", "symfony", "spring", "flutter", "firebase", "android", "ios", "wordpress", "next.js", "bootstrap")),
    ("Données et intelligence artificielle", "Data and AI", ("power bi", "tableau", "excel avancé", "pandas", "numpy", "scikit-learn",
                                       "tensorflow", "pytorch", "keras", "spss", "stata", "sas", "qgis", "arcgis", "analyse de données",
                                       "apprentissage automatique", "machine learning", "deep learning", "statistiques", "data science",
                                       "data analysis", "statistics", "visualisation de données", "big data", "kobo", "kobotoolbox", "odk", "eviews")),
    ("Outils et environnement", "Tools", ("git", "github", "gitlab", "docker", "linux", "windows", "jira", "trello", "notion",
                                       "microsoft office", "office", "word", "excel", "powerpoint", "google workspace", "canva", "figma",
                                       "photoshop", "autocad", "ms project", "postman", "aws", "azure", "gcp")),
    ("Gestion de projet", "Project management", ("gestion de projet", "project management", "planification", "suivi-évaluation",
                                       "suivi et évaluation", "monitoring and evaluation", "cadre logique", "agile", "scrum", "prince2", "pmp")),
    ("Communication et relations", "Communication", ("communication", "prise de parole", "rédaction", "négociation", "animation",
                                       "public speaking", "writing", "leadership", "travail en équipe", "teamwork", "médiation", "plaidoyer")),
    ("Laboratoire et terrain", "Laboratory and fieldwork", ("pcr", "elisa", "microscopie", "chromatographie", "spectrophotométrie",
                                       "enquête", "enquêtes", "collecte de données", "terrain", "fieldwork", "survey", "surveys", "cartographie")),
]


def categorize_skills(items: list[str], language: str = "fr") -> list[str]:
    """« Python, Django, SQL, Git » → [« Programmation : Python, SQL », « Développement web et mobile : Django », « Outils : Git »].
    Les lignes déjà rangées (« Catégorie : … ») sont gardées telles quelles."""
    kept: list[str] = []
    buckets: dict[int, list[str]] = {}
    other: list[str] = []
    for it in items:
        if ":" in it and len(it.split(":", 1)[0].split()) <= 5:
            kept.append(it.strip())
            continue
        for raw in split_outside_parens(it.replace(";", ","), ","):
            sk = raw.strip(" .")
            if not sk:
                continue
            key = re.sub(r"\s*\([^)]*\)", "", sk).strip().lower()
            idx = next((i for i, (_fr, _en, words) in enumerate(SKILL_CATEGORIES) if key in words), None)
            words = sk.split()
            common = len(words) > 1 and words[1][:1].islower() and not words[0].isupper()
            nice = (sk[:1].lower() + sk[1:]) if common and language == "fr" else sk
            if idx is None:
                other.append(nice)
            else:
                buckets.setdefault(idx, []).append(nice)
    out = list(kept)
    for i in sorted(buckets):
        fr, en, _ = SKILL_CATEGORIES[i]
        vals = list(dict.fromkeys(buckets[i]))
        out.append(f"{en if language == 'en' else fr} : {', '.join(vals)}" if language != "en" else f"{en}: {', '.join(vals)}")
    if other:
        vals = list(dict.fromkeys(other))
        out.append(f"Autres compétences : {', '.join(vals)}" if language != "en" else f"Other skills: {', '.join(vals)}")
    return out


def order_skills_for(items: list[str], keywords: list[str]) -> list[str]:
    """Les catégories qui recoupent les thèmes de la bourse passent en premier."""
    kw = [k.lower() for k in keywords if k]

    def rank(line: str) -> int:
        low = line.lower()
        last = low.startswith(("outils", "tools", "autres", "other", "bureautique", "office"))
        return (1 if last else 0, -sum(1 for k in kw if k in low))
    return sorted(items, key=rank)


def of_org_fr(org: str) -> str:
    """« Université de Lomé » → « de l'Université de Lomé » ; « Lycée de Tokoin » → « du Lycée de Tokoin »."""
    org = org.strip()
    first = org.split()[0].lower() if org else ""
    if org[:1] in VOWEL and (first in FEM_ORGS or first in MASC_ORGS):
        return "de l'" + org
    if first in FEM_ORGS:
        return "de la " + org
    if first in MASC_ORGS:
        return "du " + org
    return "de " + org if org[:1] not in VOWEL else "d'" + org


FR_MONTH_ABBR = {"jan": "janvier", "janv": "janvier", "fév": "février", "fev": "février", "févr": "février", "mars": "mars",
                 "mar": "mars", "avr": "avril", "mai": "mai", "juin": "juin", "juil": "juillet", "aoû": "août", "aou": "août",
                 "sep": "septembre", "sept": "septembre", "oct": "octobre", "nov": "novembre", "déc": "décembre", "dec": "décembre",
                 "feb": "février", "apr": "avril", "may": "mai", "jun": "juin", "jul": "juillet", "aug": "août"}


def start_of_fr(dates: str) -> str:
    """« Oct 2024 - Aujourd'hui » → « octobre 2024 » ; « 2023 - 2024 » → « 2023 »."""
    m = re.match(r"\s*([A-Za-zéûÉ]+)\.?\s+((?:19|20)\d{2})", dates or "")
    if m:
        key = m.group(1).lower()
        full = FR_MONTH_ABBR.get(key[:4]) or FR_MONTH_ABBR.get(key[:3]) or (key if key in FR_MONTH_ABBR.values() else "")
        if full:
            return f"{full} {m.group(2)}"
    m = re.search(r"(?:19|20)\d{2}", dates or "")
    return m.group(0) if m else ""
