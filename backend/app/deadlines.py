"""Dates limites : état, priorité et message prêt à afficher.

    expiree  : date dépassée (pour une bourse annuelle, on annonce la session suivante estimée)
    urgente  : 14 jours ou moins
    bientot  : 45 jours ou moins
    ouverte  : plus de 45 jours
    inconnue : pas de date publiée (candidature au fil de l'eau ou calendrier par pays)

La priorité sert au tri « urgentes d'abord » : 1 urgente, 2 bientôt, 3 ouverte, 4 inconnue, 5 expirée.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .i18n import is_en, t
from .models import Scholarship

URGENT_DAYS = 14
SOON_DAYS = 45
PRIORITY = {"urgente": 1, "bientot": 2, "ouverte": 3, "inconnue": 4, "expiree": 5}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"]


def fr_date(d: date) -> str:
    """Date en toutes lettres dans la langue de la requête (« 1er mars 2027 » ou « 1 March 2027 »)."""
    if is_en():
        return f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    return f"{d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]} {d.year}"


def fr_month(d: date) -> str:
    return f"{(MONTHS_EN if is_en() else MONTHS)[d.month - 1]} {d.year}"


def add_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 février
        return d.replace(year=d.year + 1, day=28)


@dataclass
class DeadlineInfo:
    status: str
    priority: int
    days_left: int | None
    label: str
    next_expected: date | None


def deadline_info(s: Scholarship, today: date | None = None) -> DeadlineInfo:
    today = today or date.today()
    d = s.deadline
    # Conférence sans date limite d'inscription : on se fie à la date de l'événement
    if d is None and s.kind == "conference" and s.event_start:
        d = s.event_start
    # Session passée connue (bourse annuelle dont la date a été reportée par estimation)
    if s.deadline_estimated and s.previous_deadline and s.previous_deadline < today and d and d >= today:
        days = (d - today).days
        return DeadlineInfo(
            "expiree", PRIORITY["expiree"], None,
            t(f"Session close le {fr_date(s.previous_deadline)}. Prochaine session attendue en {fr_month(d)}.",
              f"Applications closed on {fr_date(s.previous_deadline)}. Next round expected in {fr_month(d)}."),
            d,
        )
    if s.status == "expiree" or (d and d < today):
        nxt = add_year(d) if (d and s.recurring) else None
        if d:
            label = t(f"Date limite dépassée depuis le {fr_date(d)}.", f"Deadline passed on {fr_date(d)}.")
            if nxt:
                label += t(f" Rendez-vous annuel : prochaine session attendue en {fr_month(nxt)}.",
                           f" Annual programme: next round expected in {fr_month(nxt)}.")
        else:
            label = t("Cette opportunité n'accepte plus de candidatures.", "This opportunity is no longer accepting applications.")
        return DeadlineInfo("expiree", PRIORITY["expiree"], (d - today).days if d else None, label, nxt)
    if not d:
        if s.kind == "stage":
            return DeadlineInfo("inconnue", PRIORITY["inconnue"], None,
                                t("Candidatures toute l'année ou selon les offres publiées : consultez la page officielle.",
                                  "Applications are accepted year-round or as offers are published: see the official page."), None)
        return DeadlineInfo("inconnue", PRIORITY["inconnue"], None,
                            t("Date limite non publiée : consultez le calendrier sur le site officiel.",
                              "Deadline not published: see the calendar on the official website."), None)
    days = (d - today).days
    suffix = ""
    if s.deadline_estimated and not s.verified_at:
        # Date reconstituée d'après la session précédente : on ne l'affiche jamais comme une date exacte
        # Statut « ouverte » (pas de badge Urgent sur une date incertaine) ; la priorité garde l'urgence pour le tri.
        urgency = "urgente" if days <= URGENT_DAYS else "bientot" if days <= SOON_DAYS else "ouverte"
        return DeadlineInfo("ouverte", PRIORITY[urgency], days,
                            t(f"Ouverture des candidatures attendue d'ici {fr_month(d)}, d'après la session précédente. La date exacte n'est pas encore confirmée : vérifiez-la sur le site officiel.",
                              f"Applications expected by {fr_month(d)}, based on the previous round. The exact date is not yet confirmed: check it on the official website."), None)
    if days == 0:
        return DeadlineInfo("urgente", 1, 0, t(f"Clôture aujourd'hui{suffix}.", f"Closes today{suffix}."), None)
    if days <= URGENT_DAYS:
        return DeadlineInfo("urgente", 1, days, t(f"Urgent : clôture dans {days} jour{'s' if days > 1 else ''}, le {fr_date(d)}{suffix}.",
                                                f"Urgent: closes in {days} day{'s' if days > 1 else ''}, on {fr_date(d)}{suffix}."), None)
    if days <= SOON_DAYS:
        return DeadlineInfo("bientot", 2, days, t(f"Clôture dans {days} jours, le {fr_date(d)}{suffix}.", f"Closes in {days} days, on {fr_date(d)}{suffix}."), None)
    return DeadlineInfo("ouverte", 3, days, t(f"Date limite : {fr_date(d)}{suffix}.", f"Deadline: {fr_date(d)}{suffix}."), None)


def is_open(s: Scholarship, today: date | None = None) -> bool:
    return deadline_info(s, today).status != "expiree"
