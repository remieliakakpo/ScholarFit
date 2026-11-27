"""Découverte de bourses dans le monde entier par l'IA.

À chaque passage, Claude cherche sur le web (outil de recherche serveur) les bourses d'une
partie du monde, en tournant sur une cinquantaine de zones (régions, pays, publics, domaines, niveaux, stages, conférences) qui couvrent toute la planète : au bout de quelques
passages, tous les continents ont été parcourus, puis on recommence pour trouver les nouvelles
bourses et les nouvelles dates.

Garde-fous :
- seuls les liens vers le site de l'organisme qui finance (ou son portail officiel) sont gardés ;
- chaque lien est testé avant enregistrement : un lien mort n'entre pas en base ;
- les fiches restent marquées pour l'équipe dans l'administration, jusqu'à leur relecture ;
- aucun texte n'est recopié : l'IA reformule les conditions en phrases courtes.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from ..ai.client import ask_json, ask_web
from ..config import get_settings
from ..linkcheck import BROWSER_UA, check_url
from ..models import Source
from ..vocab import DOMAINS, LEVELS

log = logging.getLogger(__name__)
STATE = Path(__file__).resolve().parent.parent.parent / ".cache" / "discovery_state.json"

ZONES = [
    ("Afrique de l'Ouest", "études dans un pays d'Afrique de l'Ouest, ou bourses réservées aux ressortissants d'Afrique de l'Ouest (Sénégal, Côte d'Ivoire, Mali, Burkina Faso, Bénin, Togo, Niger, Guinée, Ghana, Nigeria…)"),
    ("Afrique centrale", "études en Afrique centrale, ou bourses pour les ressortissants du Cameroun, du Gabon, du Congo, de la RD Congo, du Tchad, de Centrafrique"),
    ("Afrique de l'Est", "études en Afrique de l'Est (Kenya, Rwanda, Ouganda, Tanzanie, Éthiopie) ou pour ses ressortissants"),
    ("Afrique australe", "études en Afrique du Sud, Botswana, Namibie, Zambie, Zimbabwe, Mozambique, Madagascar, Maurice"),
    ("Afrique du Nord", "études au Maroc, en Tunisie, en Algérie, en Égypte, et bourses pour leurs ressortissants"),
    ("France, Belgique, Suisse, Luxembourg", "bourses pour étudiants internationaux en France, Belgique, Suisse, Luxembourg"),
    ("Allemagne, Autriche, Pays-Bas", "bourses pour étudiants internationaux en Allemagne, Autriche, Pays-Bas"),
    ("Royaume-Uni et Irlande", "bourses pour étudiants internationaux au Royaume-Uni et en Irlande"),
    ("Pays nordiques", "bourses pour étudiants internationaux en Suède, Norvège, Danemark, Finlande, Islande"),
    ("Europe du Sud", "bourses pour étudiants internationaux en Italie, Espagne, Portugal, Grèce, Malte, Chypre"),
    ("Europe centrale et de l'Est", "bourses pour étudiants internationaux en Pologne, Hongrie, Tchéquie, Roumanie, Slovaquie, Pays baltes, Russie"),
    ("Amérique du Nord", "bourses pour étudiants internationaux aux États-Unis et au Canada"),
    ("Amérique latine", "bourses pour étudiants internationaux au Mexique, Brésil, Argentine, Chili, Colombie, Pérou"),
    ("Caraïbes", "bourses d'études dans les Caraïbes ou pour les ressortissants d'Haïti, de la Jamaïque, de Cuba, de la République dominicaine"),
    ("Moyen-Orient et Golfe", "bourses pour étudiants internationaux en Arabie saoudite, aux Émirats, au Qatar, au Koweït, en Turquie, en Israël, en Jordanie"),
    ("Asie de l'Est", "bourses pour étudiants internationaux en Chine, au Japon, en Corée du Sud, à Taïwan"),
    ("Asie du Sud-Est", "bourses pour étudiants internationaux à Singapour, en Malaisie, en Thaïlande, en Indonésie, au Vietnam, aux Philippines, à Brunei"),
    ("Asie du Sud et centrale", "bourses pour étudiants internationaux en Inde, au Pakistan, au Bangladesh, au Sri Lanka, au Kazakhstan, en Ouzbékistan"),
    ("Océanie", "bourses pour étudiants internationaux en Australie, en Nouvelle-Zélande, aux Fidji"),
    ("Programmes internationaux", "bourses d'organisations internationales et de fondations ouvertes à plusieurs pays (ONU, UNESCO, Banque mondiale, BAD, BID, OPEP, fondations privées, Commonwealth, Francophonie, Union africaine, Erasmus Mundus)"),
    # Pays d'Afrique où l'on étudie le plus souvent sur place
    ("Ghana et Nigeria", "bourses pour étudier au Ghana ou au Nigeria (universités publiques, fondations, gouvernement) et bourses réservées aux Ghanéens et Nigérians"),
    ("Sénégal, Côte d'Ivoire, Togo, Bénin", "bourses pour étudier au Sénégal, en Côte d'Ivoire, au Togo ou au Bénin (instituts régionaux, 2iE, CESAG, universités) et bourses nationales ou de coopération pour leurs ressortissants"),
    ("Maroc, Égypte, Rwanda, Kenya", "bourses pour étudiants africains au Maroc (AMCI), en Égypte, au Rwanda et au Kenya"),
    # Publics et domaines
    ("Bourses pour les femmes", "bourses, prix et programmes réservés aux femmes et aux filles, en particulier en sciences, ingénierie, informatique, entrepreneuriat et leadership, dans le monde entier"),
    ("Informatique, numérique et données", "bourses en informatique, intelligence artificielle, science des données, cybersécurité et télécoms, financées par des universités, des entreprises (Google, Microsoft, Meta, Huawei…) et des fondations"),
    ("Santé et médecine", "bourses en médecine, santé publique, pharmacie, soins infirmiers et recherche biomédicale (OMS, fondations, universités)"),
    ("Agriculture, environnement et climat", "bourses en agronomie, sécurité alimentaire, environnement, climat et énergie renouvelable (FAO, CGIAR, RUFORUM, fondations)"),
    ("Ingénierie, sciences et mathématiques", "bourses en ingénierie, physique, chimie, mathématiques et sciences fondamentales (AIMS, TWAS, universités techniques)"),
    ("Droit, économie, gestion et sciences sociales", "bourses en droit, économie, finance, gestion, MBA, politiques publiques, relations internationales et sciences sociales"),
    ("Arts, lettres, journalisme et éducation", "bourses en arts, architecture, design, cinéma, musique, langues, journalisme et sciences de l'éducation"),
    ("Réfugiés et étudiants à revenus modestes", "bourses réservées aux personnes réfugiées ou déplacées (DAFI, UNHCR, universités) et aux étudiants de familles à revenus modestes ou en situation de handicap"),
    # Niveaux
    ("Bourses de licence (premier cycle)", "bourses d'études de licence ou bachelor complètes pour étudiants internationaux qui sortent du lycée"),
    ("Doctorat et post-doctorat", "bourses de doctorat, contrats doctoraux, bourses post-doctorales et de recherche ouvertes aux chercheurs internationaux"),
    ("Écoles d'été, échanges et formations courtes", "bourses pour écoles d'été, semestres d'échange, formations courtes et programmes de leadership pour étudiants"),
    ("Stages dans les organisations internationales", "stages et programmes jeunes professionnels ouverts aux étudiants et jeunes diplômés : ONU et agences, Banque mondiale, FMI, BAD, Union africaine, OIF, Union européenne, ONG internationales", "stage"),
    ("Stages en Afrique et pour les Africains", "stages rémunérés en entreprise, en administration ou en ONG en Afrique, ou réservés aux étudiants africains à l'étranger", "stage"),
    ("Stages à l'ONU et dans ses agences", "stages au siège et dans les bureaux pays de l'ONU, du PNUD, de l'UNICEF, de l'OMS, de la FAO, de l'UNESCO, du HCR, du PAM, de l'OIT, de l'ONUDI, de l'OIM", "stage"),
    ("Stages dans les banques et institutions financières", "stages à la Banque mondiale, au FMI, à la Banque africaine de développement, à la BCEAO, à la BOAD, à la BEI, à la BID, à l'OCDE", "stage"),
    ("Stages dans les institutions africaines et francophones", "stages à l'Union africaine, à la CEDEAO, à l'UEMOA, à la CEMAC, à l'OIF, à l'AUF, à l'Afreximbank, à Smart Africa", "stage"),
    ("Stages dans les institutions européennes", "stages à la Commission européenne (Blue Book), au Parlement européen, au Conseil de l'Europe, dans les agences de l'UE et dans les programmes de volontariat international", "stage"),
    ("Stages en Europe", "stages rémunérés en entreprise, en laboratoire ou en ONG en France, Allemagne, Belgique, Suisse, Pays-Bas, Royaume-Uni, ouverts aux étudiants étrangers", "stage"),
    ("Stages en Amérique du Nord", "stages rémunérés aux États-Unis et au Canada ouverts aux étudiants internationaux (Mitacs, programmes d'entreprises, organisations internationales à New York, Washington, Montréal)", "stage"),
    ("Stages en Asie, au Moyen-Orient et en Océanie", "stages rémunérés ouverts aux étudiants internationaux au Japon, en Corée, en Chine, à Singapour, aux Émirats, au Qatar, en Australie", "stage"),
    ("Stages dans les ONG et fondations internationales", "stages dans les grandes ONG et fondations (Croix-Rouge, MSF, Oxfam, Save the Children, Plan International, Fondation Gates, Mastercard Foundation)", "stage"),
    ("Conférences et sommets pour étudiants", "conférences, sommets, forums et écoles d'été qui offrent une prise en charge (travel grant, bourse de participation) aux étudiants et jeunes chercheurs", "conference"),
    ("Conférences en Afrique", "conférences scientifiques, sommets de la jeunesse et forums en Afrique ouverts aux étudiants, avec dates et conditions de participation", "conference"),
]

SEARCH_SYSTEM = """Tu es documentaliste pour une plateforme d'opportunités pour étudiants (bourses d'études, stages, conférences).
Tu cherches sur le web des opportunités réelles et en cours (ou dont la prochaine session s'ouvre dans les 12 mois),
du bac au post-doctorat.
Règles :
- Ne cite que des opportunités précises (pas des listes génériques d'agrégateurs).
- Pour chaque opportunité, donne l'adresse de la page OFFICIELLE de l'organisme qui finance ou de son portail de candidature,
  jamais celle d'un blog ou d'un agrégateur.
- Donne la prochaine date limite si elle est publiée, les niveaux, les nationalités éligibles, le pays d'études,
  ce qui est financé, les conditions, les pièces à fournir et comment postuler.
- N'invente rien : si une information n'est pas sur une source fiable, dis qu'elle est inconnue."""

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["bourse", "stage", "conference"]},
        "title": {"type": "string"},
        "organization": {"type": "string"},
        "official_url": {"type": "string"},
        "event_start": {"type": ["string", "null"]},
        "event_end": {"type": ["string", "null"]},
        "city": {"type": ["string", "null"]},
        "remote": {"type": "boolean"},
        "duration": {"type": ["string", "null"]},
        "summary": {"type": "string"},
        "levels": {"type": "array", "items": {"type": "string", "enum": list(LEVELS)}},
        "study_countries": {"type": "array", "items": {"type": "string"}},
        "eligible_nationalities": {"type": "array", "items": {"type": "string"}},
        "domains": {"type": "array", "items": {"type": "string", "enum": list(DOMAINS)}},
        "languages": {"type": "array", "items": {"type": "string"}},
        "amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
        "amount_period": {"type": ["string", "null"], "enum": ["mois", "an", "total", None]},
        "coverage": {"type": "array", "items": {"type": "string", "enum": ["frais", "logement", "voyage", "allocation", "assurance"]}},
        "full_funding": {"type": "boolean"},
        "deadline": {"type": ["string", "null"]},
        "max_age": {"type": ["integer", "null"]},
        "requirements": {"type": "array", "items": {"type": "string", "enum": [
            "cv", "lettre", "recommandation", "releves", "test_langue", "projet_recherche", "passeport", "diplome",
            "certificat_medical", "lettre_admission", "photo", "portfolio", "justificatif_revenus"]}},
        "eligibility": {"type": "array", "items": {"type": "string"}},
        "application_steps": {"type": "array", "items": {"type": "string"}},
        "apply_via": {"type": "string", "enum": ["direct", "universite", "ambassade", "etablissement", "nomination"]},
        "target_groups": {"type": "array", "items": {"type": "string", "enum": ["femmes", "refugie", "handicap", "revenus_modestes", "premiere_generation"]}},
    },
    "required": ["kind", "event_start", "event_end", "city", "remote", "duration", "title", "organization", "official_url", "summary", "levels", "study_countries", "eligible_nationalities",
                 "domains", "languages", "amount", "currency", "amount_period", "coverage", "full_funding", "deadline",
                 "max_age", "requirements", "eligibility", "application_steps", "apply_via", "target_groups"],
    "additionalProperties": False,
}
LIST_SCHEMA = {
    "type": "object",
    "properties": {"scholarships": {"type": "array", "items": ITEM_SCHEMA}},
    "required": ["scholarships"],
    "additionalProperties": False,
}

STRUCTURE_SYSTEM = """Transforme ces notes de recherche en fiches JSON (bourses, stages ou conférences). Réponds uniquement avec le JSON.
- kind : bourse, stage ou conference. event_start / event_end : dates de la conférence ou du stage (AAAA-MM-JJ) ou null.
- city : ville ; remote : participation en ligne possible ; duration : durée d'un stage en clair.
- levels : diplôme financé (BAC = première année d'université, BAC3 = licence/bachelor, BAC5 = master, BAC7 = doctorat ou post-doc).
- study_countries, eligible_nationalities : codes ISO alpha-2 ; eligible_nationalities = ["ALL"] si ouvert à tous ;
  groupes possibles : AFRICA, EU, FRANCOPHONIE, DEVELOPING, COMMONWEALTH, LATAM, ASIA. study_countries vide si plusieurs pays au choix.
- deadline : AAAA-MM-JJ ou null. Ne garde pas une bourse dont la date est passée sans session suivante annoncée.
- summary : deux phrases en français, avec tes mots. eligibility : conditions détaillées en phrases courtes, en français.
- application_steps : étapes concrètes en français, dans l'ordre (vide si inconnues).
- domains : ["tous"] si tous les domaines.
- target_groups : public réservé (femmes, refugie, handicap, revenus_modestes, premiere_generation), vide sinon.
- study_countries d'un stage : pays où se déroule le stage.
- Ne garde que les bourses dont official_url est une adresse complète (https://…) d'un site officiel. N'invente rien."""


def _zone_index(n: int) -> list[int]:
    try:
        start = json.loads(STATE.read_text())["next"]
    except (OSError, ValueError, KeyError):
        start = 0
    idx = [(start + i) % len(ZONES) for i in range(n)]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"next": (start + n) % len(ZONES)}))
    return idx


def discover_zone(name: str, scope: str, max_searches: int, kind: str = "bourse") -> list[dict]:
    today = date.today().isoformat()
    what = {"bourse": "bourses distinctes, de préférence entièrement financées",
            "stage": "stages distincts, de préférence rémunérés",
            "conference": "conférences distinctes, de préférence avec prise en charge des participants"}[kind]
    notes = ask_web(
        SEARCH_SYSTEM,
        f"Nous sommes le {today}. Zone : {name}. Cherche : {scope}. Trouve jusqu'à 15 {what}, "
        "ouvertes aux étudiants étrangers ou africains, avec leur page officielle. Privilégie celles qui ne sont pas les plus connues.",
        max_searches=max_searches,
    )
    if not notes:
        return []
    data = ask_json(STRUCTURE_SYSTEM, notes[:60000], LIST_SCHEMA, effort="low", max_tokens=16000)
    return (data or {}).get("scholarships", [])


def run_ai_discovery(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    from .collector import upsert  # import local : évite une boucle d'import

    s = get_settings()
    if not s.ai_enabled or not s.ai_discovery_enabled:
        raise RuntimeError("découverte IA inactive : ajoute ANTHROPIC_API_KEY dans backend/.env")
    created = updated = 0
    with httpx.Client(headers={"User-Agent": BROWSER_UA}, timeout=15, follow_redirects=True) as http:
        for i in _zone_index(int(cfg.get("zones_per_run", 5))):
            name, scope, *rest = ZONES[i]
            kind = rest[0] if rest else "bourse"
            found = discover_zone(name, scope, s.ai_discovery_max_searches, kind)
            log.info("Zone %s : %d bourse(s) proposée(s)", name, len(found))
            for rec in found:
                url = (rec.get("official_url") or "").strip()
                if not url.startswith("http"):
                    continue
                status, final, _code = check_url(url, http)
                if status == "casse":
                    log.info("Lien mort ignoré : %s", url)
                    continue
                rec["kind"] = rec.get("kind") or kind
                for k in ("deadline", "event_start", "event_end"):
                    if rec.get(k):
                        try:
                            rec[k] = date.fromisoformat(rec[k])
                        except ValueError:
                            rec[k] = None
                rec["domains"] = rec.get("domains") or ["tous"]
                rec["eligible_nationalities"] = rec.get("eligible_nationalities") or ["ALL"]
                rec["link_status"] = status
                rec["link_final_url"] = final
                sch, is_new = upsert(db, rec, source)
                created += is_new
                updated += not is_new
            db.commit()
    return created, updated
