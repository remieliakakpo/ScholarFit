"""Alertes : nouvelles bourses pour le profil, recherches sauvegardées, rappels J-30, J-7, J-1.

Chaque alerte est d'abord enregistrée en base (affichée dans l'interface). `send_alert_emails`
envoie ensuite, à chaque passage de la collecte automatique, **un seul e-mail par personne** qui
regroupe ses nouvelles alertes (y compris celles de l'accompagnement), avec un lien pour se
désabonner. Pas d'e-mail si la personne a refusé les alertes ou n'a pas confirmé son adresse.
Pour ajouter WhatsApp ou Telegram : un second canal dans `send_alert_emails`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import i18n
from .deadlines import fr_date
from .details import content
from .i18n import t
from .matching import Criteria, missing_minimum, rank
from .models import Alert, Scholarship, User

log = logging.getLogger("alertes")
REMINDER_DAYS = (30, 7, 1)
UNSUBSCRIBE = "desabonner"
EMAIL_WINDOW_DAYS = 3  # une alerte plus ancienne n'est plus envoyée (elle reste visible sur le site)
MAX_ITEMS_PER_EMAIL = 15


def _add(db: Session, user: User, key: str, kind: str, message: str, scholarship_id: int | None) -> bool:
    exists = db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.key == key)).first()
    if exists:
        return False
    db.add(Alert(user_id=user.id, key=key, kind=kind, message=message, scholarship_id=scholarship_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


def run_alerts(db: Session, today: date | None = None, new_since_days: int = 7) -> int:
    today = today or date.today()
    since = datetime.now(timezone.utc) - timedelta(days=new_since_days)
    created = 0
    scholarships = list(db.scalars(select(Scholarship).where(Scholarship.status != "expiree")))
    for user in db.scalars(select(User)):
        token = i18n.set_lang(user.lang or "fr")  # messages dans la langue choisie sur le site
        try:
            created += _user_alerts(db, user, scholarships, today, since)
            created += _saved_search_alerts(db, user, today)
        finally:
            i18n._lang.reset(token)
    db.commit()
    return created


def _user_alerts(db: Session, user: User, scholarships: list[Scholarship], today: date, since: datetime) -> int:
    created = 0
    # 1. Rappels de date limite pour les candidatures pas encore envoyées
    for app in user.applications:
        s = app.scholarship
        if app.status not in ("a_preparer", "en_cours") or not s.deadline:
            continue
        days = (s.deadline - today).days
        for d in REMINDER_DAYS:
            if days == d or (d == 1 and days == 0):
                title = content(s, "title")
                created += _add(db, user, f"rappel-{s.id}-J{d}", "rappel",
                                t(f"Plus que {days} jour(s) pour « {title} » (date limite le {fr_date(s.deadline)}).",
                                  f"Only {days} day(s) left for \"{title}\" (deadline {fr_date(s.deadline)})."), s.id)
    # 2. Nouvelles bourses correspondant au profil
    if user.profile is None:
        return created
    c = Criteria.from_profile(user.profile, today)
    if missing_minimum(c):
        return created
    fresh = [s for s in scholarships if s.collected_at and _aware(s.collected_at) >= since]
    results, _ = rank(fresh, c, today, limit=10)
    for m in results:
        if m.score >= 60:
            title = content(m.scholarship, "title")
            created += _add(db, user, f"nouvelle-{m.scholarship.id}", "nouvelle_bourse",
                            t(f"Nouvelle bourse pour vous : « {title} » (score {m.score}/100).",
                              f"New scholarship for you: \"{title}\" (score {m.score}/100)."), m.scholarship.id)
    return created


def _saved_search_alerts(db: Session, user: User, today: date) -> int:
    """Nouvelles fiches (collectées depuis le dernier passage) qui répondent à une recherche sauvegardée."""
    from .routers.scholarships import FILTER_KEYS, search

    created = 0
    now = datetime.now(timezone.utc)
    for ss in user.saved_searches:
        if not ss.alerts_enabled:
            continue
        since = _aware(ss.last_checked_at or ss.created_at or now)
        filters = {k: v for k, v in (ss.filters or {}).items() if k in FILTER_KEYS}
        for k in ("deadline_after", "deadline_before"):
            if isinstance(filters.get(k), str):
                try:
                    filters[k] = date.fromisoformat(filters[k])
                except ValueError:
                    filters.pop(k)
        try:
            items, _ = search(db, today=today, extra_where=Scholarship.collected_at >= since, **filters)
        except TypeError:  # filtre enregistré illisible : on l'ignore plutôt que de bloquer les autres
            items = []
        for s in items[:10]:
            title = content(s, "title")
            created += _add(db, user, f"recherche-{ss.id}-{s.id}", "recherche",
                            t(f"Nouvelle offre pour votre recherche « {ss.name} » : « {title} ».",
                              f"New opportunity for your search \"{ss.name}\": \"{title}\"."), s.id)
        ss.last_checked_at = now
    return created


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- e-mails
def unsubscribe_link(user: User) -> str:
    from .mailer import link
    from .security import create_link_token

    return link(f"/desabonner?token={create_link_token(user, UNSUBSCRIBE, 365 * 24 * 60)}")


def _email_body(user: User, alerts: list[Alert]) -> tuple[str, str]:
    from .mailer import link

    en = user.lang == "en"
    lines = []
    for a in alerts[:MAX_ITEMS_PER_EMAIL]:
        line = f"- {a.message}"
        if a.scholarship_id:
            line += f"\n  {link(f'/bourses/{a.scholarship_id}')}"
        lines.append(line)
    more = len(alerts) - MAX_ITEMS_PER_EMAIL
    if more > 0:
        lines.append(f"… {'and' if en else 'et'} {more} {'more' if en else 'de plus'}")
    n = len(alerts)
    if en:
        subject = f"ScholarFit: {n} new alert{'s' if n > 1 else ''}"
        body = ("Hello,\n\nHere is what's new for you on ScholarFit:\n\n" + "\n".join(lines)
                + f"\n\nYour space: {link('/mes-bourses')}\n\n"
                f"To stop receiving these e-mails: {unsubscribe_link(user)}\n")
    else:
        subject = f"ScholarFit : {n} nouvelle{'s' if n > 1 else ''} alerte{'s' if n > 1 else ''}"
        body = ("Bonjour,\n\nVoici les nouveautés pour vous sur ScholarFit :\n\n" + "\n".join(lines)
                + f"\n\nVotre espace : {link('/mes-bourses')}\n\n"
                f"Pour ne plus recevoir ces e-mails : {unsubscribe_link(user)}\n")
    return subject, body


def send_alert_emails(db: Session) -> int:
    """Un e-mail par personne avec ses alertes pas encore envoyées. Renvoie le nombre d'e-mails."""
    from .config import get_settings
    from .mailer import send_mail

    now = datetime.now(timezone.utc)
    window = now - timedelta(days=EMAIL_WINDOW_DAYS)
    pending = list(db.scalars(
        select(Alert).where(Alert.emailed_at.is_(None), Alert.created_at >= window).order_by(Alert.user_id, Alert.created_at)
    ))
    by_user: dict[int, list[Alert]] = {}
    for a in pending:
        by_user.setdefault(a.user_id, []).append(a)
    sent = 0
    smtp = bool(get_settings().smtp_host)
    for alerts in by_user.values():
        user = alerts[0].user
        if user.profile is not None and not user.profile.alerts_opt_in:
            for a in alerts:
                a.emailed_at = now  # refus : on ne les enverra pas plus tard
            continue
        if not user.email_verified:
            continue  # partiront après confirmation de l'adresse, si elles sont encore récentes
        subject, body = _email_body(user, alerts)
        ok = send_mail(user.email, subject, body, headers={"List-Unsubscribe": f"<{unsubscribe_link(user)}>"})
        if ok:
            sent += 1
        if ok or not smtp:  # sans SMTP (développement), le message est écrit une fois dans le journal
            for a in alerts:
                a.emailed_at = now
    db.commit()
    return sent
