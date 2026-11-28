"""Fiche détaillée d'une bourse : conditions en clair, pièces à fournir, étapes pour postuler.

Les conditions sont d'abord déduites des champs structurés (niveau, nationalité, âge, moyenne,
langue, public ciblé), puis complétées par les conditions propres à la bourse (champ
``eligibility``). Les étapes sont générées selon le mode de candidature (``apply_via``), sauf si
la bourse a ses propres étapes (``application_steps``).
"""
from __future__ import annotations

from . import i18n
from .geo import REGIONS, region_of
from .i18n import t
from .models import Scholarship
from .vocab import COUNTRIES, DOMAINS, LEVELS, NATIONALITY_GROUPS

REQUIREMENTS: dict[str, tuple[str, str]] = {
    "cv": ("CV", "CV à jour d'une à deux pages, au format demandé (souvent Europass en Europe, résumé d'une page aux États-Unis)."),
    "lettre": ("Lettre de motivation", "Lettre adaptée à cette bourse : votre projet d'études, pourquoi ce pays et ce programme, ce que vous ferez ensuite. Respectez la limite de mots indiquée."),
    "recommandation": ("Lettres de recommandation", "En général deux lettres d'enseignants ou d'employeurs qui vous connaissent bien, signées, sur papier à en-tête. Prévenez vos référents au moins un mois avant."),
    "releves": ("Relevés de notes", "Relevés officiels des dernières années d'études (souvent depuis le bac), avec traduction certifiée en anglais ou en français si nécessaire."),
    "test_langue": ("Test de langue", "Résultat officiel d'un test reconnu (IELTS, TOEFL, DELF/DALF, TCF, TestDaF…), en cours de validité (souvent moins de 2 ans)."),
    "projet_recherche": ("Projet de recherche", "Projet de 2 à 5 pages : question de recherche, méthode, calendrier et intérêt du sujet. Idéalement validé par un futur directeur de recherche."),
    "passeport": ("Passeport", "Copie de la page d'identité d'un passeport valide pendant toute la durée des études."),
    "diplome": ("Copie du diplôme", "Copie certifiée conforme du dernier diplôme obtenu (ou attestation de réussite), traduite si nécessaire."),
    "certificat_medical": ("Certificat médical", "Certificat médical récent, parfois sur un formulaire imposé par l'organisme."),
    "lettre_admission": ("Lettre d'admission", "Lettre d'admission ou de pré-acceptation de l'université d'accueil, si la bourse l'exige avant la candidature."),
    "photo": ("Photo d'identité", "Photo d'identité récente au format demandé."),
    "portfolio": ("Portfolio", "Sélection de travaux (arts, design, architecture) au format numérique demandé."),
    "justificatif_revenus": ("Justificatif de revenus", "Pièces montrant les revenus du foyer, pour les bourses sur critères sociaux."),
}

GROUP_LABELS = {
    "AFRICA": "ressortissants d'un pays africain",
    "EU": "ressortissants de l'Union européenne",
    "FRANCOPHONIE": "ressortissants d'un pays de la Francophonie",
    "DEVELOPING": "ressortissants d'un pays en développement (liste de l'organisme)",
    "COMMONWEALTH": "ressortissants d'un pays du Commonwealth éligible",
    "LATAM": "ressortissants d'Amérique latine ou des Caraïbes",
    "ASIA": "ressortissants d'un pays d'Asie",
}
TARGET_LABELS = {
    "refugie": "réservée aux personnes réfugiées ou déplacées",
    "handicap": "réservée aux étudiants en situation de handicap",
    "revenus_modestes": "réservée aux candidats issus de familles à revenus modestes",
    "premiere_generation": "réservée aux étudiants de première génération à l'université",
    "femmes": "réservée aux candidates femmes",
}
COVERAGE_LABELS = {"frais": "frais de scolarité", "logement": "logement", "voyage": "billet d'avion",
                   "allocation": "allocation mensuelle", "assurance": "assurance santé"}

REQUIREMENTS_EN: dict[str, tuple[str, str]] = {
    "cv": ("CV", "An up-to-date one- or two-page CV in the requested format (often Europass in Europe, a one-page resume in the United States)."),
    "lettre": ("Cover letter", "A letter written for this scholarship: your study plan, why this country and this programme, and what you will do afterwards. Respect the stated word limit."),
    "recommandation": ("Reference letters", "Usually two signed letters on letterhead from teachers or employers who know you well. Contact your referees at least one month in advance."),
    "releves": ("Transcripts", "Official transcripts for your recent years of study (often since secondary school), with a certified English or French translation if needed."),
    "test_langue": ("Language test", "An official result from a recognised test (IELTS, TOEFL, DELF/DALF, TCF, TestDaF…), still valid (often less than 2 years old)."),
    "projet_recherche": ("Research proposal", "A 2 to 5 page proposal: research question, method, timeline and relevance of the topic. Ideally approved by a future supervisor."),
    "passeport": ("Passport", "A copy of the identity page of a passport valid for the whole study period."),
    "diplome": ("Copy of your degree", "A certified copy of your most recent degree (or a certificate of completion), translated if needed."),
    "certificat_medical": ("Medical certificate", "A recent medical certificate, sometimes on a form provided by the organisation."),
    "lettre_admission": ("Admission letter", "An admission or pre-acceptance letter from the host university, if the scholarship requires it before you apply."),
    "photo": ("ID photo", "A recent ID photo in the requested format."),
    "portfolio": ("Portfolio", "A selection of your work (arts, design, architecture) in the requested digital format."),
    "justificatif_revenus": ("Proof of income", "Documents showing household income, for need-based scholarships."),
}
GROUP_LABELS_EN = {
    "AFRICA": "nationals of an African country",
    "EU": "nationals of the European Union",
    "FRANCOPHONIE": "nationals of a member country of the Francophonie",
    "DEVELOPING": "nationals of a developing country (as listed by the organisation)",
    "COMMONWEALTH": "nationals of an eligible Commonwealth country",
    "LATAM": "nationals of Latin America or the Caribbean",
    "ASIA": "nationals of an Asian country",
}
TARGET_LABELS_EN = {
    "refugie": "reserved for refugees and displaced people",
    "handicap": "reserved for students with disabilities",
    "revenus_modestes": "reserved for applicants from low-income families",
    "premiere_generation": "reserved for first-generation university students",
    "femmes": "reserved for women",
}
LANG_NAMES = {"fr": "français", "en": "anglais", "de": "allemand", "es": "espagnol", "pt": "portugais", "it": "italien",
              "zh": "chinois", "ja": "japonais", "ko": "coréen", "ru": "russe", "ar": "arabe", "tr": "turc", "hu": "hongrois",
              "nl": "néerlandais"}
LANG_NAMES_EN = {"fr": "French", "en": "English", "de": "German", "es": "Spanish", "pt": "Portuguese", "it": "Italian",
                 "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ru": "Russian", "ar": "Arabic", "tr": "Turkish",
                 "hu": "Hungarian", "nl": "Dutch"}


def requirement_label(code: str) -> tuple[str, str]:
    """(libellé, détail par défaut) d'une pièce dans la langue de la requête."""
    if i18n.is_en() and code in REQUIREMENTS_EN:
        return REQUIREMENTS_EN[code]
    return REQUIREMENTS.get(code, (code, ""))


def content(s: Scholarship, field: str):
    """Champ rédigé (titre, résumé, conditions…) : version anglaise si elle existe et que la requête est en anglais."""
    value = getattr(s, field)
    if i18n.is_en():
        en = ((s.translations or {}).get("en") or {}).get(field)
        if en:
            return en
    return value


def _names(codes: list[str], limit: int = 8) -> str:
    table = i18n.countries(COUNTRIES)
    names = [table.get(c, c) for c in codes]
    if len(names) > limit:
        return ", ".join(names[:limit]) + t(f" et {len(names) - limit} autres pays", f" and {len(names) - limit} other countries")
    return ", ".join(names)


def regions(s: Scholarship) -> list[str]:
    out = []
    for c in s.study_countries or []:
        r = region_of(c)
        if r and r not in out:
            out.append(r)
    return out


def _when_where(s: Scholarship) -> list[str]:
    out = []
    if s.event_start:
        from .deadlines import fr_date

        if s.event_end and s.event_end != s.event_start:
            out.append(t(f"Dates : du {fr_date(s.event_start)} au {fr_date(s.event_end)}.",
                         f"Dates: {fr_date(s.event_start)} to {fr_date(s.event_end)}."))
        else:
            out.append(t(f"Date : {fr_date(s.event_start)}.", f"Date: {fr_date(s.event_start)}."))
    place = s.city or ""
    if s.study_countries:
        place = ", ".join(filter(None, [place, _names(s.study_countries)]))
    if place:
        out.append(t(f"Lieu : {place}", f"Location: {place}")
                   + (t(" (participation en ligne possible).", " (online participation possible).") if s.remote else "."))
    elif s.remote:
        out.append(t("En ligne / à distance.", "Online / remote."))
    duration = content(s, "duration")
    if duration:
        out.append(t(f"Durée : {duration}.", f"Duration: {duration}."))
    return out


def eligibility_notes(s: Scholarship) -> list[str]:
    notes: list[str] = []
    kind = s.kind or "bourse"
    bourse = kind == "bourse"
    levels = i18n.loc(LEVELS, i18n.LEVELS_EN)
    domains = i18n.loc(DOMAINS, i18n.DOMAINS_EN)
    groups_l = GROUP_LABELS_EN if i18n.is_en() else GROUP_LABELS
    targets_l = TARGET_LABELS_EN if i18n.is_en() else TARGET_LABELS
    coverage_l = i18n.loc(COVERAGE_LABELS, i18n.COVERAGE_EN)
    if not bourse:
        notes.extend(_when_where(s))
    if s.levels:
        head = t("Niveau financé : ", "Funded level: ") if bourse else t("Niveau d'études visé : ", "Study level: ")
        notes.append(head + " ; ".join(levels.get(l, l) for l in s.levels) + ".")
    nat = s.eligible_nationalities or ["ALL"]
    if "ALL" in nat:
        line = t("Ouverte à toutes les nationalités", "Open to all nationalities")
    else:
        groups = [groups_l[n] for n in nat if n in groups_l]
        countries = [n for n in nat if n not in NATIONALITY_GROUPS]
        parts = groups + ([t("ressortissants de : ", "nationals of: ") + _names(countries)] if countries else [])
        line = t("Réservée aux ", "Reserved for ") + t(" ou ", " or ").join(parts)
    if s.excluded_nationalities:
        table = i18n.countries(COUNTRIES)
        excl = [groups_l.get(n, table.get(n, n)) for n in s.excluded_nationalities]
        line += t(f" (sauf : {', '.join(excl)})", f" (except: {', '.join(excl)})")
    notes.append(line + ".")
    if bourse:
        if s.study_countries:
            notes.append(t("Études dans : ", "Study in: ") + _names(s.study_countries) + ".")
        else:
            notes.append(t("Études possibles dans plusieurs pays (selon le programme ou l'université choisie).",
                           "Study possible in several countries (depending on the programme or university chosen)."))
    if s.domains and "tous" not in s.domains:
        head = t("Domaines financés : ", "Funded fields: ") if bourse else t("Domaines : ", "Fields: ")
        notes.append(head + ", ".join(domains.get(d, d).lower() for d in s.domains) + ".")
    else:
        notes.append(t("Tous les domaines sont acceptés.", "All fields are accepted."))
    if s.max_age:
        notes.append(t(f"Âge maximum : {s.max_age} ans (en général à la date limite ou au début du programme).",
                       f"Maximum age: {s.max_age} (usually at the deadline or at the start of the programme)."))
    if s.min_grade is not None:
        notes.append(t(f"Excellent dossier attendu : moyenne d'au moins {s.min_grade:g}/20 environ (ou équivalent).",
                       f"Strong academic record expected: an average of about {s.min_grade:g}/20 or more (or equivalent)."))
    if s.language_tests:
        tests = t(" ou ", " or ").join(f"{k} {m:g}" for k, m in s.language_tests.items())
        notes.append(t(f"Niveau de langue prouvé par un test : {tests} minimum.", f"Language level shown by a test: at least {tests}."))
    elif s.languages:
        names = LANG_NAMES_EN if i18n.is_en() else LANG_NAMES
        notes.append(t("Langue d'enseignement : ", "Language of instruction: ")
                     + t(" ou ", " or ").join(names.get(l, l) for l in s.languages) + ".")
    for g in s.target_groups or []:
        label = targets_l.get(g, g)
        notes.append(label[:1].upper() + label[1:] + ".")
    notes.extend(content(s, "eligibility") or [])
    if kind == "stage" and s.amount:
        period = s.amount_period or "mois"
        if i18n.is_en():
            period = {"mois": "month", "an": "year", "total": "total"}.get(period, period)
            notes.append(f"Paid internship: about {s.amount:,.0f} {s.currency or ''} per {period}.")
        else:
            notes.append(f"Stage rémunéré : environ {s.amount:,.0f} {s.currency or ''} par {period}.".replace(",", " "))
    if s.coverage:
        head = t("Ce qui est couvert : ", "What is covered: ") if bourse else t("Prise en charge : ", "Covered: ")
        notes.append(head + ", ".join(coverage_l.get(c, c) for c in s.coverage)
                     + (t(" (financement complet).", " (full funding).") if s.full_funding else "."))
    return notes


def documents(s: Scholarship) -> list[dict]:
    out = []
    detail = content(s, "documents_detail") or {}
    for code in s.requirements or []:
        label, default = requirement_label(code)
        text = detail.get(code) or default
        if code == "test_langue" and s.language_tests and not detail.get(code):
            text += t(" Scores demandés : ", " Required scores: ") + ", ".join(f"{k} {m:g}" for k, m in s.language_tests.items()) + "."
        out.append({"code": code, "label": label, "detail": text})
    for i, extra in enumerate(content(s, "extra_documents") or []):
        out.append({"code": f"autre_{i + 1}", "label": extra, "detail": ""})
    if not out:
        out.append({"code": "voir_site", "label": t("Liste des pièces sur le site officiel", "Document list on the official website"),
                    "detail": t("L'organisme ne publie pas de liste unique : consultez l'appel à candidatures.",
                                "The organisation does not publish a single list: see the call for applications.")})
    return out


def application_steps(s: Scholarship) -> list[str]:
    own = content(s, "application_steps")
    if own:
        return list(own)
    url = s.apply_url or s.official_url
    if (s.kind or "bourse") == "stage":
        return [
            t(f"Consultez l'offre de stage sur la page officielle (lien en bas de cette page) et vérifiez le niveau d'études, la durée et les dates demandés.",
              f"Read the internship offer on the official page (link at the bottom of this page) and check the required level of study, duration and dates."),
            t("Créez votre compte sur le portail de recrutement de l'organisation et activez les alertes pour votre domaine.",
              "Create an account on the organisation's recruitment portal and turn on alerts for your field."),
            t("Adaptez votre CV et votre lettre de motivation à la mission (ScholarFit peut vous aider à les préparer).",
              "Tailor your CV and cover letter to the assignment (ScholarFit can help you prepare them)."),
            t("Préparez une attestation d'inscription de votre université ou votre dernier diplôme, souvent demandés.",
              "Prepare a certificate of enrolment from your university or your latest degree, which are often requested."),
            t("Envoyez votre candidature avant la date limite de l'offre, puis préparez l'entretien ou le test écrit.",
              "Submit your application before the deadline, then prepare for the interview or written test."),
        ]
    if s.kind == "conference":
        return [
            t(f"Lisez le programme et les conditions de participation sur le site officiel (lien en bas de cette page).",
              f"Read the programme and participation conditions on the official website (link at the bottom of this page)."),
            t("Si la conférence propose une prise en charge (travel grant, bourse de participation), déposez votre demande avant la date limite.",
              "If the conference offers funding (travel grant, participation grant), apply before the deadline."),
            t("Préparez ce qui est demandé : résumé de votre recherche ou de votre projet, CV, lettre de motivation.",
              "Prepare what is requested: an abstract of your research or project, a CV and a cover letter."),
            t("Une fois accepté(e), demandez la lettre d'invitation pour le visa et réservez votre voyage.",
              "Once accepted, request the invitation letter for your visa and book your travel."),
        ]
    steps = [
        t(f"Lisez l'appel à candidatures complet sur le site officiel (lien en bas de cette page) et vérifiez que vous remplissez chaque condition ci-dessus.",
          f"Read the full call for applications on the official website (link at the bottom of this page) and check that you meet each condition above."),
    ]
    via = s.apply_via or "direct"
    if via == "universite":
        steps.append(t("Choisissez votre programme et faites d'abord votre demande d'admission à l'université : la bourse se demande en même temps ou juste après.",
                       "Choose your programme and apply for admission to the university first: the scholarship application is made at the same time or just after."))
    elif via == "ambassade":
        steps.append(t("Contactez l'ambassade ou le service culturel du pays d'accueil dans votre pays : c'est lui qui publie le calendrier et reçoit les dossiers.",
                       "Contact the embassy or cultural service of the host country in your country: it publishes the calendar and receives applications."))
    elif via == "etablissement":
        steps.append(t("Faites-vous admettre dans un établissement partenaire : c'est l'établissement d'accueil qui présente votre candidature à la bourse.",
                       "Get admitted to a partner institution: the host institution submits your application for the scholarship."))
    elif via == "nomination":
        steps.append(t("Demandez à votre université ou à votre futur directeur de recherche de proposer votre candidature : la bourse fonctionne sur nomination.",
                       "Ask your university or your future supervisor to nominate you: this scholarship works by nomination."))
    else:
        steps.append(t("Créez votre compte sur le portail de candidature de l'organisme.",
                       "Create an account on the organisation's application portal."))
    needs = set(s.requirements or [])
    prep = []
    if "recommandation" in needs:
        prep.append(t("demandez vos lettres de recommandation (au moins un mois avant)", "request your reference letters (at least one month ahead)"))
    if "test_langue" in needs:
        prep.append(t("passez ou planifiez votre test de langue", "take or book your language test"))
    if "releves" in needs or "diplome" in needs:
        prep.append(t("faites certifier et traduire relevés et diplômes", "have your transcripts and degrees certified and translated"))
    if "projet_recherche" in needs:
        prep.append(t("rédigez votre projet de recherche avec votre futur encadrant", "write your research proposal with your future supervisor"))
    if prep:
        steps.append(t("Préparez les pièces qui prennent du temps : ", "Prepare the documents that take time: ") + ", ".join(prep) + ".")
    steps.append(t("Rédigez votre lettre de motivation et mettez votre CV au format demandé (ScholarFit peut vous aider à les préparer).",
                   "Write your cover letter and put your CV in the requested format (ScholarFit can help you prepare them)."))
    steps.append(t("Rassemblez toutes les pièces de la liste, vérifiez-les une dernière fois, puis déposez votre dossier avant la date limite.",
                   "Gather every document on the list, check them one last time, then submit your application before the deadline."))
    steps.append(t("Gardez l'accusé de réception et préparez l'entretien éventuel : la sélection prend souvent plusieurs mois.",
                   "Keep the acknowledgement of receipt and prepare for a possible interview: selection often takes several months."))
    return steps


def region_labels(codes: list[str]) -> list[str]:
    labels = i18n.loc(REGIONS, i18n.REGIONS_EN)
    return [labels.get(c, c) for c in codes]
