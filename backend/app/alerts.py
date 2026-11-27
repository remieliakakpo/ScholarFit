"""Alertes intelligentes : nouvelles bourses correspondant au profil et rappels J-30, J-14, J-7, J-3, J-1.

Le MVP enregistre les alertes en base (affichées dans l'interface) et les « envoie » via
``send`` qui écrit dans la console. Pour brancher l'e-mail (SMTP, Brevo, Resend…) ou
WhatsApp (API Cloud de Meta, Twilio), il suffit de remplacer ``send``.
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
from .models import Alert, Application, Scholarship, User
from .visibility import public_filter

log = logging.getLogger("alertes")
REMINDER_DAYS = (30, 14, 7, 3, 1)


def send(db: Session, user: User, key: str, kind: str, message: str, scholarship_id: int | None) -> None:
    """Envoie l'alerte par e-mail (module mailer : console, SMTP, Brevo ou Resend selon .env)."""
    from .mailer import email_button, send_email

    if kind == "accompagnement":
        if key.startswith("acc-msg-") and _recent_message_email(db, user):
            return  # un e-mail de messagerie au plus toutes les 30 minutes : le reste est visible sur le site
        is_advisor = user.advisor is not None and not key.endswith("-demande")
        send_email(db, user.email, t("Votre accompagnement ScholarFit", "Your ScholarFit support"),
                   t(f"Bonjour,\n\n{message}", f"Hello,\n\n{message}"),
                   button=email_button(t("Ouvrir mon espace", "Open my space"),
                                       "/admin" if key.endswith("-demande") else ("/conseiller" if is_advisor else "/accompagnement")),
                   kind="accompagnement", key=f"{key}-u{user.id}")
        return
    if kind == "rappel":
        subject = t("Rappel : date limite proche", "Reminder: deadline approaching")
        intro = t("Bonjour,\n\nUne candidature de votre suivi arrive à échéance.", "Hello,\n\nAn application in your tracker is nearing its deadline.")
        button = email_button(t("Terminer ma candidature", "Finish my application"),
                              f"/postuler/{scholarship_id}" if scholarship_id else "/suivi")
    else:
        subject = t("Nouvelle bourse pour votre profil", "New scholarship matching your profile")
        intro = t("Bonjour,\n\nUne nouvelle opportunité correspond à votre profil.", "Hello,\n\nA new opportunity matches your profile.")
        button = email_button(t("Voir la fiche", "View the listing"), f"/bourses/{scholarship_id}" if scholarship_id else "/bourses")
    outro = t("Vous recevez ce message parce que les alertes sont activées dans votre profil. Vous pouvez les désactiver à tout moment depuis la page Profil.",
              "You are receiving this message because alerts are turned on in your profile. You can turn them off at any time from your Profile page.")
    send_email(db, user.email, subject, f"{intro}\n\n{message}\n\n{outro}", button=button, kind=kind,
               key=f"{key}-u{user.id}")


def _recent_message_email(db: Session, user: User) -> bool:
    from .models import EmailLog

    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    rows = db.scalars(select(EmailLog.created_at).where(EmailLog.to == user.email, EmailLog.kind == "accompagnement",
                                                       EmailLog.key.like("acc-msg-%"))).all()
    return any(_aware(r) >= since for r in rows)


def send_digest(db: Session, user: User, items: list[tuple[str, int]]) -> None:
    """Un seul e-mail pour toutes les nouvelles bourses trouvées lors d'un passage."""
    from .mailer import email_button, send_email

    lines = "\n".join(f"• {m}" for m, _ in items)
    n = len(items)
    subject = t("Nouvelles bourses pour votre profil", "New scholarships matching your profile") if n > 1 else \
        t("Nouvelle bourse pour votre profil", "New scholarship matching your profile")
    outro = t("Vous recevez ce message parce que les alertes sont activées dans votre profil. Vous pouvez les désactiver à tout moment depuis la page Profil.",
              "You are receiving this message because alerts are turned on in your profile. You can turn them off at any time from your Profile page.")
    button = email_button(t("Voir mes bourses", "View my scholarships"), "/mes-bourses") if n > 1 else \
        email_button(t("Voir la fiche", "View the listing"), f"/bourses/{items[0][1]}")
    send_email(db, user.email, subject, t("Bonjour,\n\nVoici les nouvelles opportunités qui correspondent à votre profil :",
                                          "Hello,\n\nHere are the new opportunities that match your profile:") + f"\n\n{lines}\n\n{outro}",
               button=button, kind="nouvelle_bourse", key=f"digest-u{user.id}-" + "-".join(str(i) for _, i in items)[:100])


def _add(db: Session, user: User, key: str, kind: str, message: str, scholarship_id: int | None, notify: bool = True) -> bool:
    exists = db.scalars(select(Alert).where(Alert.user_id == user.id, Alert.key == key)).first()
    if exists:
        return False
    db.add(Alert(user_id=user.id, key=key, kind=kind, message=message, scholarship_id=scholarship_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    if notify and (user.profile is None or user.profile.alerts_opt_in):
        send(db, user, key, kind, message, scholarship_id)
    return True


def run_alerts(db: Session, today: date | None = None, new_since_days: int = 7) -> int:
    today = today or date.today()
    since = datetime.now(timezone.utc) - timedelta(days=new_since_days)
    created = 0
    scholarships = list(db.scalars(select(Scholarship).where(public_filter(), Scholarship.status != "expiree")))
    for user in db.scalars(select(User)):
        token = i18n.set_lang(user.lang or "fr")  # messages dans la langue choisie sur le site
        try:
            created += _user_alerts(db, user, scholarships, today, since)
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
    # 2. Nouvelles bourses correspondant au profil
    if user.profile is None:
        return created
    c = Criteria.from_profile(user.profile, today)
    if missing_minimum(c):
        return created
    # seulement les bourses ajoutées après l'inscription (pas tout le catalogue de départ)
    since = max(since, _aware(user.created_at)) if user.created_at else since
    fresh = [s for s in scholarships if s.collected_at and _aware(s.collected_at) >= since]
    results, _ = rank(fresh, c, today, limit=10)
    digest: list[tuple[str, int]] = []
    for m in results:
        if m.score >= 60:
            title = content(m.scholarship, "title")
            msg = t(f"Nouvelle bourse pour vous : « {title} » (score {m.score}/100).",
                    f"New scholarship for you: \"{title}\" (score {m.score}/100).")
            if _add(db, user, f"nouvelle-{m.scholarship.id}", "nouvelle_bourse", msg, m.scholarship.id, notify=False):
                created += 1
                digest.append((msg, m.scholarship.id))
    if digest and user.profile.alerts_opt_in:
        send_digest(db, user, digest)
    return created


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
