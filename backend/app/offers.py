"""Offres d'accompagnement : postuler seul (gratuit), Standard et Premium.

Les prix se règlent dans .env (OFFER_STANDARD_PRICE, OFFER_PREMIUM_PRICE, en F CFA).
L'offre conseillée dépend du profil : niveau visé, nombre de bourses visées, besoins, et ce que
la personne a répondu à la dernière étape du questionnaire.
"""
from __future__ import annotations

from . import i18n
from .config import get_settings
from .i18n import t
from .models import Profile

HELP_PREFERENCES = {
    "seul": "Je préfère postuler seul",
    "standard": "Je veux un accompagnement standard",
    "premium": "Je veux un accompagnement complet",
    "ne_sait_pas": "Je ne sais pas encore",
}
HELP_PREFERENCES_EN = {
    "seul": "I prefer to apply on my own",
    "standard": "I would like standard support",
    "premium": "I would like full support",
    "ne_sait_pas": "I am not sure yet",
}


def help_preferences() -> dict[str, str]:
    return i18n.loc(HELP_PREFERENCES, HELP_PREFERENCES_EN)


def price_label(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " F CFA" if amount else t("Gratuit", "Free")


def catalog() -> list[dict]:
    s = get_settings()
    return [
        {
            "code": "autonome",
            "name": t("Je postule seul", "I apply on my own"),
            "price": 0,
            "currency": "XOF",
            "price_label": price_label(0),
            "description": t("Vous suivez les étapes de chaque fiche et déposez vous-même votre candidature sur le site officiel.",
                             "You follow the steps on each listing and submit your application yourself on the official website."),
            "features": [
                t("Matching et score pour toutes les bourses", "Matching and score for every scholarship"),
                t("Conditions, pièces à fournir et étapes pour chaque bourse", "Conditions, required documents and steps for each scholarship"),
                t("Premier dossier CV et lettre offert, puis abonnement à {p} par mois".replace("{p}", price_label(s.subscription_price)),
                  "First CV and letter pack free, then a {p} monthly subscription".replace("{p}", price_label(s.subscription_price))),
                t("Suivi de vos candidatures et rappels avant les dates limites", "Application tracking and reminders before deadlines"),
            ],
            "max_scholarships": None,
        },
        {
            "code": "standard",
            "name": t("Accompagnement Standard", "Standard support"),
            "price": s.offer_standard_price,
            "currency": "XOF",
            "price_label": price_label(s.offer_standard_price),
            "description": t("Un expert prépare votre dossier et dépose lui-même votre candidature à une bourse.",
                             "An expert prepares your application and submits it for you to one scholarship."),
            "features": [
                t("1 bourse choisie avec vous", "1 scholarship chosen with you"),
                t("CV et lettre de motivation adaptés par l'expert (2 révisions)", "CV and cover letter tailored by the expert (2 revisions)"),
                t("Vérification de toutes les pièces du dossier", "Check of every document in your application"),
                t("Dépôt de la candidature par l'expert, avec preuve de dépôt", "Application submitted by the expert, with proof of submission"),
                t("Suivi jusqu'au résultat", "Follow-up until the result"),
            ],
            "max_scholarships": 1,
        },
        {
            "code": "premium",
            "name": t("Accompagnement Premium", "Premium support"),
            "price": s.offer_premium_price,
            "currency": "XOF",
            "price_label": price_label(s.offer_premium_price),
            "description": t("Un expert prépare et dépose vos candidatures à trois bourses, jusqu'à l'entretien et au visa.",
                             "An expert prepares and submits your applications to three scholarships, through to the interview and visa."),
            "features": [
                t("Tout l'accompagnement Standard, pour 3 bourses", "Everything in Standard support, for 3 scholarships"),
                t("Révisions illimitées du CV et des lettres", "Unlimited revisions of your CV and letters"),
                t("Rédaction du projet d'études ou de recherche", "Writing of your study or research proposal"),
                t("Conseils pour les lettres de recommandation", "Guidance on reference letters"),
                t("Entretien blanc en visio", "Mock interview by video call"),
                t("Aide au visa si vous êtes retenu", "Visa support if you are selected"),
            ],
            "max_scholarships": 3,
        },
    ]


def recommend(p: Profile | None) -> str:
    """Code de l'offre conseillée pour ce profil."""
    if p is None:
        return "standard"
    pref = p.help_preference
    if pref in ("seul", "standard", "premium"):
        base = {"seul": "autonome"}.get(pref, pref)
    else:
        base = None
    planned = p.applications_planned or 0
    demanding = p.target_level == "BAC7" or planned >= 3 or "refugie" in (p.situations or [])
    if base == "autonome":
        return "autonome"
    if base == "premium" or demanding:
        return "premium"
    return "standard"


def with_recommendation(p: Profile | None) -> list[dict]:
    rec = recommend(p)
    return [{**o, "recommended": o["code"] == rec} for o in catalog()]


def paid_offer(code: str) -> dict | None:
    return next((o for o in catalog() if o["code"] == code and o["price"] > 0), None)
