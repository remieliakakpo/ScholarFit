"""Envoi des e-mails de ScholarFit, partagé par tous les modules : compte (confirmation de l'adresse,
mot de passe oublié), rappels de dates limites, reçus de paiement, accompagnement.

Deux façons d'envoyer :

    send_mail(to, subject, text, html=None)            e-mail déjà mis en forme (comptes)
    send_email(db, to, subject, text, button=..., kind=..., key=...)
                                                       e-mail aux couleurs du site, tracé dans email_log ;
                                                       ``key`` rend l'envoi unique (rappels relancés chaque jour)

Moyen d'envoi (EMAIL_BACKEND dans .env) :
    console : affiché dans la fenêtre de l'API, liens compris (par défaut en local)
    smtp    : SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (Brevo SMTP, Gmail, OVH, Zoho…)
    brevo   : API Brevo (BREVO_API_KEY), 300 e-mails gratuits par jour
    resend  : API Resend (RESEND_API_KEY)
Sans EMAIL_BACKEND : smtp si SMTP_HOST est renseigné, sinon console. L'expéditeur est SMTP_FROM.
Un échec d'envoi est journalisé et ne fait jamais échouer la requête de l'utilisateur.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .models import EmailLog

log = logging.getLogger("e-mails")

INK = "#0b1220"
MINT = "#3ee0a8"
AMBER = "#ffb547"


@dataclass
class Button:
    label: str
    url: str


def absolute_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return get_settings().site_url.rstrip("/") + "/" + path.lstrip("/")


def email_button(label: str, path: str) -> Button:
    return Button(label, absolute_url(path))


def render_html(subject: str, text: str, button: Button | None = None, footer: str | None = None) -> str:
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    body = "".join(
        f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#1f2937">{html.escape(p).replace(chr(10), "<br>")}</p>'
        for p in paragraphs
    )
    if button:
        body += (
            f'<p style="margin:24px 0 8px"><a href="{html.escape(button.url, quote=True)}" '
            f'style="display:inline-block;background:{MINT};color:{INK};font-weight:700;font-size:15px;'
            f'text-decoration:none;padding:12px 22px;border-radius:999px">{html.escape(button.label)}</a></p>'
        )
    foot = html.escape(footer or "ScholarFit · Bourses d'études, stages et conférences dans le monde entier")
    site = html.escape(get_settings().site_url)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#eef1f5;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef1f5;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden">
<tr><td style="background:{INK};padding:20px 28px">
<span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:#ffffff">Scholar</span><span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:{MINT}">Fit</span>
<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{AMBER};margin-left:4px"></span>
</td></tr>
<tr><td style="padding:28px">
<h1 style="margin:0 0 18px;font-family:Georgia,'Times New Roman',serif;font-size:22px;line-height:1.3;color:{INK}">{html.escape(subject)}</h1>
{body}
</td></tr>
<tr><td style="padding:16px 28px 24px;border-top:1px solid #e5e7eb;font-size:12px;line-height:1.5;color:#6b7280">
{foot}<br><a href="{site}" style="color:#6b7280">{site}</a>
</td></tr>
</table></td></tr></table></body></html>"""


def _sender() -> tuple[str, str]:
    """(nom, adresse) de l'expéditeur, lus dans SMTP_FROM (« ScholarFit <no-reply@domaine.org> »)."""
    name, addr = parseaddr(get_settings().smtp_from)
    return name or "ScholarFit", addr or "no-reply@scholarfit.local"


def _deliver(
    to: str, subject: str, text: str, html_body: str | None, headers: dict[str, str] | None = None
) -> None:
    """Envoie vraiment l'e-mail ; lève une exception en cas d'échec."""
    s = get_settings()
    backend = s.mail_backend
    name, addr = _sender()
    if backend == "console":
        banner = "=" * 70
        msg = f"\n{banner}\nE-MAIL (EMAIL_BACKEND=console, il n'est pas envoyé)\nÀ : {to}\nObjet : {subject}\n\n{text}\n{banner}"
        log.warning(msg)
        print(msg, flush=True)
        return
    if backend == "smtp":
        m = EmailMessage()
        m["From"] = s.smtp_from
        m["To"] = to
        m["Subject"] = subject
        m["Message-ID"] = make_msgid(domain=addr.rsplit("@", 1)[-1] or None)
        if s.email_reply_to:
            m["Reply-To"] = s.email_reply_to
        for header, value in (headers or {}).items():
            m[header] = value
        m.set_content(text)
        if html_body:
            m.add_alternative(html_body, subtype="html")
        ctx = ssl.create_default_context()
        if s.smtp_ssl:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=ctx)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls(context=ctx)
                server.ehlo()
        with server:
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(m)
        return
    if backend == "brevo":
        payload = {"sender": {"name": name, "email": addr}, "to": [{"email": to}],
                   "subject": subject, "htmlContent": html_body or text, "textContent": text}
        if headers:
            payload["headers"] = headers
        if s.email_reply_to:
            payload["replyTo"] = {"email": s.email_reply_to}
        r = httpx.post("https://api.brevo.com/v3/smtp/email", json=payload, timeout=20,
                       headers={"api-key": s.brevo_api_key, "accept": "application/json"})
        r.raise_for_status()
        return
    if backend == "resend":
        payload = {"from": s.smtp_from, "to": [to], "subject": subject, "html": html_body or text, "text": text}
        if headers:
            payload["headers"] = headers
        if s.email_reply_to:
            payload["reply_to"] = s.email_reply_to
        r = httpx.post("https://api.resend.com/emails", json=payload, timeout=20,
                       headers={"Authorization": f"Bearer {s.resend_api_key}"})
        r.raise_for_status()
        return
    raise ValueError(f"EMAIL_BACKEND inconnu : {backend}")


def send_email(db: Session | None, to: str, subject: str, text: str, *, button: Button | None = None,
               kind: str = "autre", key: str | None = None, footer: str | None = None) -> bool:
    """Envoie un e-mail. Retourne True s'il est parti (ou affiché en console), False sinon
    (déjà envoyé avec cette clé, ou échec enregistré). Ne lève jamais d'exception."""
    s = get_settings()
    if db is not None and key and db.scalars(select(EmailLog.id).where(EmailLog.key == key)).first():
        return False
    full_text = text.strip() + (f"\n\n{button.label} : {button.url}" if button else "")
    status, error = "envoye", None
    try:
        _deliver(to, subject, full_text, render_html(subject, text, button, footer))
    except Exception as e:  # noqa: BLE001 - un e-mail perdu ne doit pas casser l'action de l'utilisateur
        status, error = "echec", str(e)[:500]
        log.warning("Échec d'envoi à %s (%s) : %s", to, subject, e)
    if db is not None:
        try:
            with db.begin_nested():  # point de sauvegarde : n'annule pas le travail en cours de l'appelant
                db.add(EmailLog(to=to, subject=subject[:300], kind=kind, key=key, backend=s.mail_backend,
                                status=status, error=error))
        except IntegrityError:  # même clé envoyée au même moment par un autre processus
            return False
    return status == "envoye"

def send_mail(
    to: str, subject: str, text: str, html: str | None = None, *, headers: dict[str, str] | None = None
) -> bool:
    """Envoie un e-mail déjà mis en forme. Renvoie False (sans lever d'erreur) si l'envoi échoue."""
    try:
        _deliver(to, subject, text, html, headers)
        if get_settings().mail_backend != "console":
            log.info("E-mail « %s » envoyé à %s", subject, to)
        return True
    except Exception:  # noqa: BLE001 - un e-mail perdu ne doit pas casser l'action de l'utilisateur
        log.exception("Échec de l'envoi de l'e-mail « %s » à %s", subject, to)
        return False


def link(path: str) -> str:
    return get_settings().frontend_url.rstrip("/") + path


def _html(greeting: str, intro: str, button: str, link: str, outro: str) -> str:
    from html import escape

    return f"""<!doctype html><html><body style="margin:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;color:#14152b">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;padding:32px">
<tr><td style="font-family:Georgia,serif;font-size:22px;font-weight:bold">Scholar<span style="color:#14a679">Fit</span></td></tr>
<tr><td style="padding-top:24px;font-size:16px;line-height:1.55">
<p style="margin:0 0 12px">{escape(greeting)}</p>
<p style="margin:0 0 24px">{escape(intro)}</p>
<p style="margin:0 0 24px"><a href="{escape(link)}" style="display:inline-block;background:#3ee0a8;color:#04140e;text-decoration:none;font-weight:bold;padding:12px 22px;border-radius:999px">{escape(button)}</a></p>
<p style="margin:0 0 8px;font-size:13px;color:#5b5d75">{escape(outro)}</p>
<p style="margin:0;font-size:12px;color:#5b5d75;word-break:break-all">{escape(link)}</p>
</td></tr></table></td></tr></table></body></html>"""


def verification_email(name: str, link: str, hours: int, en: bool = False) -> tuple[str, str, str]:
    if en:
        subject = "Confirm your email address · ScholarFit"
        greeting, intro, button = f"Hi {name},", "Welcome to ScholarFit. Please confirm your email address so we can send you your deadline reminders and recover your account if needed.", "Confirm my email"
        outro = f"This link is valid for {hours} hours. If you did not create an account, ignore this email. Link:"
    else:
        subject = "Confirmez votre adresse e-mail · ScholarFit"
        greeting, intro, button = f"Salut {name},", "Bienvenue sur ScholarFit. Confirmez votre adresse e-mail pour recevoir vos rappels de dates limites et pouvoir récupérer votre compte si besoin.", "Confirmer mon e-mail"
        outro = f"Ce lien est valable {hours} heures. Si vous n'avez pas créé de compte, ignorez cet e-mail. Lien :"
    text = f"{greeting}\n\n{intro}\n\n{button} : {link}\n\n{outro.removesuffix(' Lien :').removesuffix(' Link:')}"
    return subject, text, _html(greeting, intro, button, link, outro)


def reset_email(name: str, link: str, minutes: int, en: bool = False) -> tuple[str, str, str]:
    if en:
        subject = "Reset your password · ScholarFit"
        greeting, intro, button = f"Hi {name},", "Someone (hopefully you) asked to reset the password of your ScholarFit account. Click the button to choose a new one.", "Choose a new password"
        outro = f"This link is valid for {minutes} minutes and works only once. If you did not ask for it, ignore this email: your password stays the same. Link:"
    else:
        subject = "Réinitialisez votre mot de passe · ScholarFit"
        greeting, intro, button = f"Salut {name},", "Vous avez demandé à changer le mot de passe de votre compte ScholarFit. Cliquez sur le bouton pour en choisir un nouveau.", "Choisir un nouveau mot de passe"
        outro = f"Ce lien est valable {minutes} minutes et ne sert qu'une fois. Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : votre mot de passe ne change pas. Lien :"
    text = f"{greeting}\n\n{intro}\n\n{button} : {link}\n\n{outro.removesuffix(' Lien :').removesuffix(' Link:')}"
    return subject, text, _html(greeting, intro, button, link, outro)
