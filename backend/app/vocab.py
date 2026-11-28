"""Listes contrôlées : niveaux, domaines, pays, groupes de nationalités.

Les filtres restent fiables parce que bourses et profils utilisent les mêmes codes.
"""

LEVELS: dict[str, str] = {
    # Code = diplôme que la bourse finance (le « niveau visé » de l'étudiant)
    "BAC": "Bac (lycée, année préparatoire)",
    "BAC3": "Bac+3 : licence / bachelor",
    "BAC5": "Bac+5 : master",
    "BAC7": "Bac+7 et plus : doctorat, post-doc",
}
LEVEL_ORDER = ["BAC", "BAC3", "BAC5", "BAC7"]

# Types d'opportunités
KINDS: dict[str, str] = {
    "bourse": "Bourse d'études",
    "stage": "Stage",
    "conference": "Conférence",
    "formation": "Formation",
    "concours": "Concours",
    "echange": "Programme d'échange",
    "fellowship": "Fellowship",
    "cours_en_ligne": "Cours en ligne",
}
# Filtre « type » des routes (?kind=…) ; KIND_OR_ALL accepte aussi « tout »
KIND_PATTERN = "^(" + "|".join(KINDS) + ")$"
KIND_OR_ALL_PATTERN = "^(" + "|".join(KINDS) + "|tout)$"

DOMAINS: dict[str, str] = {
    "agriculture": "Agriculture et agronomie",
    "arts": "Arts, design et architecture",
    "biologie": "Biologie et sciences de la vie",
    "chimie": "Chimie",
    "droit": "Droit et sciences politiques",
    "economie": "Économie et gestion",
    "education": "Éducation",
    "energie": "Énergie et environnement",
    "informatique": "Informatique et numérique",
    "ingenierie": "Ingénierie",
    "langues": "Langues, lettres et humanités",
    "mathematiques": "Mathématiques et statistiques",
    "medecine": "Médecine et santé",
    "physique": "Physique",
    "relations_internationales": "Relations internationales et développement",
    "sciences_sociales": "Sciences sociales et psychologie",
    "journalisme": "Journalisme et communication",
    "tous": "Tous domaines",
}

# Tous les pays du monde (codes ISO 3166-1 alpha-2), voir app/geo.py.
from .geo import WORLD  # noqa: E402

COUNTRIES: dict[str, str] = {code: w[0] for code, w in WORLD.items()}

AFRICA = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CM", "CV", "CF", "KM", "CG", "CD", "CI", "DJ", "EG",
    "GQ", "ER", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW",
    "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST", "SN", "SC", "SL", "SO", "ZA",
    "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW",
}
EU = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
    "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}
# Pays membres de l'Organisation internationale de la Francophonie (sélection)
FRANCOPHONIE = {
    "BE", "BJ", "BF", "BI", "CM", "CA", "KM", "CG", "CD", "CI", "DJ", "FR", "GA", "GN", "HT",
    "LB", "MG", "ML", "MA", "MU", "MR", "NE", "RW", "SN", "CH", "TD", "TG", "TN", "VN",
}
# Pays à revenu faible ou intermédiaire (approximation pour le MVP)
DEVELOPING = AFRICA | {
    "HT", "IN", "VN", "LB", "BD", "PK", "NP", "KH", "LA", "BO", "PE", "CO", "ID", "PH", "AF", "MM", "LK",
    "BT", "MN", "KG", "TJ", "UZ", "TM", "YE", "PS", "SY", "JO", "IQ", "TL", "PG", "SB", "VU", "FJ", "WS",
    "TO", "KI", "TV", "GT", "HN", "NI", "SV", "EC", "PY", "VE", "CU", "DO", "JM", "BZ", "GY", "SR",
    "MD", "UA", "AM", "GE", "AZ", "AL", "BA", "MK", "XK", "ME", "RS", "BR", "MX", "AR", "TR", "TH", "MY", "IR",
}
# Pays du Commonwealth (sélection pour les bourses britanniques et du Commonwealth)
COMMONWEALTH_DEV = {
    "BD", "BW", "CM", "GA", "GH", "GM", "GY", "IN", "JM", "KE", "LK", "LS", "MW", "MZ", "NA", "NG", "PK",
    "PG", "RW", "SL", "SB", "SZ", "TG", "TO", "TZ", "UG", "VU", "WS", "ZM", "FJ", "KI", "TV", "BZ", "DM",
    "GD", "LC", "VC", "KN", "AG", "MV", "MU", "SC", "TT",
}
LATAM = {c for c, w in WORLD.items() if w[1] == "amerique"} - {"US", "CA"}
ASIA = {c for c, w in WORLD.items() if w[1] == "asie"}

NATIONALITY_GROUPS: dict[str, set[str]] = {
    "AFRICA": AFRICA,
    "EU": EU,
    "FRANCOPHONIE": FRANCOPHONIE,
    "DEVELOPING": DEVELOPING,
    "COMMONWEALTH": COMMONWEALTH_DEV,
    "LATAM": LATAM,
    "ASIA": ASIA,
}


def expand_nationalities(codes: list[str]) -> set[str] | None:
    """Transforme une liste de codes/groupes en ensemble de codes ISO. None = toutes nationalités."""
    if not codes or "ALL" in codes:
        return None
    out: set[str] = set()
    for c in codes:
        out |= NATIONALITY_GROUPS.get(c, {c})
    return out


# Mots-clés utilisés par l'extraction hors-ligne (chat, CV) pour reconnaître les domaines.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "agriculture": ["agri", "agronom", "agro"],
    "arts": ["arts", "beaux-arts", "design", "architect", "musique", "cinéma"],
    "biologie": ["bio", "génétique", "écologie", "sciences de la vie"],
    "chimie": ["chimie", "chimiste"],
    "droit": ["droit", "juridique", "juriste", "science po", "sciences po", "politique"],
    "economie": ["économ", "econom", "gestion", "finance", "commerce", "management", "marketing", "business"],
    "education": ["éducation", "enseignement", "pédagog"],
    "energie": ["énergie", "energie", "environnement", "climat", "renouvelable"],
    "informatique": ["informatique", "numérique", "data", "logiciel", "développeur", "ia ", "intelligence artificielle", "computer"],
    "ingenierie": ["ingénie", "ingenie", "génie", "mécanique", "électrique", "civil"],
    "langues": ["lettres", "langue", "littérature", "philosophie", "histoire", "linguistique"],
    "mathematiques": ["math", "statistique"],
    "medecine": ["médecine", "medecine", "santé", "pharmac", "infirmi", "dentaire"],
    "physique": ["physique"],
    "relations_internationales": ["relations internationales", "développement", "humanitaire"],
    "sciences_sociales": ["sociologie", "psycholog", "anthropolog", "sciences sociales"],
    "journalisme": ["journalisme", "communication", "média"],
}

COUNTRY_KEYWORDS: dict[str, list[str]] = {
    "FR": ["france", "français", "francais", "paris"],
    "CA": ["canada", "québec", "quebec", "montréal"],
    "DE": ["allemagne", "germany", "allemand"],
    "BE": ["belgique", "belge"],
    "CH": ["suisse"],
    "GB": ["royaume-uni", "angleterre", "uk", "londres"],
    "US": ["états-unis", "etats-unis", "usa", "amérique"],
    "JP": ["japon"],
    "CN": ["chine"],
    "KR": ["corée"],
    "HU": ["hongrie"],
    "TR": ["turquie"],
    "MA": ["maroc"],
    "SN": ["sénégal", "senegal", "sénégalais", "senegalais"],
    "CI": ["côte d'ivoire", "cote d'ivoire", "ivoirien"],
    "CM": ["cameroun", "camerounais"],
    "ML": ["mali", "malien"],
    "BF": ["burkina"],
    "BJ": ["bénin", "benin", "béninois"],
    "TG": ["togo", "togolais"],
    "GN": ["guinée", "guinéen"],
    "TN": ["tunisie", "tunisien"],
    "DZ": ["algérie", "algérien"],
    "CD": ["rdc", "rd congo", "congolais"],
    "MG": ["madagascar", "malgache"],
    "NE": ["niger", "nigérien"],
    "HT": ["haïti", "haitien", "haïtien"],
    "NL": ["pays-bas", "hollande"],
    "IT": ["italie"],
    "ES": ["espagne"],
    "SE": ["suède"],
    "AU": ["australie"],
    "IE": ["irlande"],
}

# Tous les autres pays : on reconnaît au moins leur nom français.
for _code, _w in WORLD.items():
    _name = _w[0].lower()
    if _name not in COUNTRY_KEYWORDS.setdefault(_code, []):
        COUNTRY_KEYWORDS[_code].append(_name)
