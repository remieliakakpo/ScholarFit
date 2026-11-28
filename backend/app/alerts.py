"""Alertes : nouvelles bourses pour le profil, recherches sauvegardées, rappels J-30, J-14, J-7, J-3, J-1.

Chaque alerte est d'abord enregistrée en base (affichée dans l'interface). Deux façons de l'envoyer :
- tout de suite, pour ce qui n'attend pas : messages de l'accompagnement et rappels de date limite
  (`send`, un e-mail aux couleurs du site, tracé dans email_log) ;
- regroupées, pour les nouvelles bourses et les recherches sauvegardées : `send_alert_emails` envoie,
  à chaque passage de la collecte automatique, **un seul e-mail par personne**, avec un lien pour se
  désabonner.
Pas d'e-mail si la personne a refusé les alertes ou n'a pas confirmé son adresse.
Pour ajouter WhatsApp ou Telegram : un second canal dans `send` et `send_alert_emails`.
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
from .visibility import public_filter

log = logging.getLogger("alertes")
REMINDER_DAYS = (30, 14, 7, 3, 1)
UNSUBSCRIBE = "desabonner"
EMAIL_WINDOW_DAYS = 3  # une alerte plus ancienne n'est plus envoyée (elle reste visible sur le site)
MAX_ITEMS_PER_EMAIL = 15
IMMEDIATE = {"accompagnement", "rappel"}  # envoyées tout de suite ; le reste part dans le résumé


def _wants_email(user: User) -> bool:
    return user.email_verified and (user.profile is None or user.profile.alerts_opt_in)


def send(db: Session, user: User, key: str, kind: str, message: str, scholarship_id: int | None) -> bool:
    """E-mail immédiat (accompagnement, rappel de date limite). Renvoie True s'il est parti."""
    from .mailer import email_button, send_email

    if kind == "accompagnement":
        if key.startswith("acc-msg-") and _recent_message_email(db, user):
            return True  # un e-mail de messagerie au plus toutes les 30 minutes : le reste est visible sur le site
        is_advisor = user.advisor is not None and not key.endswith("-demande")
        return send_email(db, user.email, t("Votre accompagnement ScholarFit", "Your ScholarFit support"),
                          t(f"Bonjour,\n\n{message}", f"Hello,\n\n{message}"),
                          button=email_button(t("Ouvrir mon espace", "Open my space"),
                                              "/admin" if key.endswith("-demande") else ("/conseiller" if is_advisor else "/accompagnement")),
                          kind="accompagnement", key=f"{key}-u{user.id}")
    subject = t("Rappel : date limite proche", "Reminder: deadline approaching")
    intro = t("Bonjour,\n\nUne candidature de votre suivi arrive à échéance.", "Hello,\n\nAn application in your tracker is nearing its deadline.")
    button = email_button(t("Terminer ma candidature", "Finish my application"),
                          f"/postuler/{scholarship_id}" if scholarship_id else "/suivi")
    outro = t("Vous recevez ce message parce que les alertes sont activées dans votre profil. Vous pouvez les désactiver à tout moment depuis la page Profil.",
              "You are receiving this message because alerts are turned on in your profile. You can turn them off at any time from your Profile page.")
    return send_email(db, user.email, subject, f"{intro}\n\n{message}\n\n{outro}", button=button, kind=kind,
                      key=f"{key}-u{user.id}")


def _recent_message_email(db: Session, user: User) -> bool:
    from .models import EmailLog

    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    rows = db.scalars(select(EmailLog.created_at).where(EmailLog.to == user.email, EmailLog.kind == "accompagnement",
                                                       EmailLog.key.like("acc-msg-%"))).all()
    return any(_aware(r) >= since for r in rows)


def _add(db: Session, user: User, key: str, kind: str, message: str, scholarship_id: int | None, notify: bool = True) -> bool:
    exists = db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.key == key)).first()
    if exists:
        return False
    alert = Alert(user_id=user.id, key=key, kind=kind, message=message, scholarship_id=scholarship_id)
    db.add(alert)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    if notify and kind in IMMEDIATE:
        if not _wants_email(user) or send(db, user, key, kind, message, scholarship_id):
            alert.emailed_at = datetime.now(timezone.utc)  # pas dans le résumé
    return True


def run_alerts(db: Session, today: date | None = None, new_since_days: int = 7) -> int:
    from .site_settings import enabled_kinds

    today = today or date.today()
    since = datetime.now(timezone.utc) - timedelta(days=new_since_days)
    created = 0
    scholarships = list(db.scalars(select(Scholarship).where(
        public_filter(), Scholarship.status != "expiree", Scholarship.kind.in_(enabled_kinds(db)))))
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
        if days < 0:
            continue
        # Palier le plus proche atteint (J-30, J-14, J-7, J-3, J-1) : un seul rappel par palier, même si
        # la collecte n'a pas tourné le jour exact.
        reached = [d for d in REMINDER_DAYS if days <= d]
        if not reached:
            continue
        d = min(reached)
        title = content(s, "title")
        if days == 0:
            msg = t(f"C'est aujourd'hui la date limite pour « {title} ».", f"Today is the deadline for \"{title}\".")
        elif days == 1:
            msg = t(f"Plus qu'un jour pour « {title} » (date limite le {fr_date(s.deadline)}).",
                    f"Only one day left for \"{title}\" (deadline {fr_date(s.deadline)}).")
        else:
            msg = t(f"Plus que {days} jours pour « {title} » (date limite le {fr_date(s.deadline)}).",
                    f"Only {days} days left for \"{title}\" (deadline {fr_date(s.deadline)}).")
        created += _add(db, user, f"rappel-{s.id}-J{d}", "rappel", msg, s.id)
    # 2. Nouvelles bourses correspondant au profil (envoyées dans le résumé)
    if user.profile is None:
        return created
    c = Criteria.from_profile(user.profile, today)
    if missing_minimum(c):
        return created
    # seulement les bourses ajoutées après l'inscription (pas tout le catalogue de départ)
    since = max(since, _aware(user.created_at)) if user.created_at else since
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
    from .site_settings import enabled_kinds

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
            items, _ = search(db, today=today, extra_where=Scholarship.collected_at >= since, enabled=enabled_kinds(db), **filters)
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


# ---------------------------------------------------------------- résumé par e-mail
def unsubscribe_link(user: User) -> str:
    from .mailer import link
    from .security import create_link_token

    return link(f"/desabonner?token={create_link_token(user, UNSUBSCRIBE, 365 * 24 * 60)}")


def _email_body(user: User, alerts: list[Alert]) -> tuple[str, str]:
    from .mailer import link

    en = user.lang == "en"
    lines = []
    for a in alerts[:MAX_ITEMS_PER_EMAIL]:
        line = f"• {a.message}"
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
                + f"\n\nTo stop receiving these e-mails: {unsubscribe_link(user)}")
    else:
        subject = f"ScholarFit : {n} nouvelle{'s' if n > 1 else ''} alerte{'s' if n > 1 else ''}"
        body = ("Bonjour,\n\nVoici les nouveautés pour vous sur ScholarFit :\n\n" + "\n".join(lines)
                + f"\n\nPour ne plus recevoir ces e-mails : {unsubscribe_link(user)}")
    return subject, body


def send_alert_emails(db: Session) -> int:
    """Un e-mail par personne avec ses alertes pas encore envoyées. Renvoie le nombre d'e-mails."""
    from .config import get_settings
    from .mailer import email_button, render_html, send_mail

    now = datetime.now(timezone.utc)
    window = now - timedelta(days=EMAIL_WINDOW_DAYS)
    pending = list(db.scalars(
        select(Alert).where(Alert.emailed_at.is_(None), Alert.created_at >= window).order_by(Alert.user_id, Alert.created_at)
    ))
    by_user: dict[int, list[Alert]] = {}
    for a in pending:
        by_user.setdefault(a.user_id, []).append(a)
    sent = 0
    really_sends = get_settings().mail_backend != "console"
    for alerts in by_user.values():
        user = alerts[0].user
        if user.profile is not None and not user.profile.alerts_opt_in:
            for a in alerts:
                a.emailed_at = now  # refus : on ne les enverra pas plus tard
            continue
        if not user.email_verified:
            continue  # partiront après confirmation de l'adresse, si elles sont encore récentes
        token = i18n.set_lang(user.lang or "fr")
        try:
            subject, body = _email_body(user, alerts)
            button = email_button(t("Voir mon espace", "Open my space"), "/mes-bourses")
            ok = send_mail(user.email, subject, f"{body}\n\n{button.label} : {button.url}", render_html(subject, body, button),
                           headers={"List-Unsubscribe": f"<{unsubscribe_link(user)}>"})
        finally:
            i18n._lang.reset(token)
        if ok:
            sent += 1
        if ok or not really_sends:  # en développement, le message est écrit une fois dans le journal
            for a in alerts:
                a.emailed_at = now
    db.commit()
    return sent
