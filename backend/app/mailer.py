"""Envoi d'e-mails (vérification d'adresse, mot de passe oublié).

Sans SMTP_HOST, rien n'est envoyé : en développement, le message est écrit dans le journal de l'API
pour pouvoir cliquer sur le lien ; en production, seul un avertissement est écrit (pas de lien).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.smtp_host:
        if s.is_dev:
            log.info("[E-MAIL → %s] %s\n%s", to, subject, body)
        else:
            log.warning("E-mail non envoyé à %s (« %s ») : SMTP_HOST n'est pas configuré", to, subject)
        return False
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if s.smtp_port == 465:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
        with server:
            if s.smtp_port != 465 and s.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException):
        log.exception("Échec de l'envoi de l'e-mail à %s", to)
        return False


def link(path: str) -> str:
    return get_settings().frontend_url.rstrip("/") + path
