"""Vérification des liens officiels : chaque bourse affichée doit renvoyer vers une page qui répond.

    ok          : la page répond (code 2xx)
    redirige    : la page a déménagé ; on garde la nouvelle adresse comme lien de candidature
    casse       : 404, 410, domaine introuvable… la bourse est signalée dans /admin
    non_verifie : pas encore testé, ou site injoignable pour une raison passagère (on réessaiera)

Certains sites refusent les robots (403, 429) ou les requêtes HEAD : on réessaie en GET et on ne
déclare « cassé » que les erreurs franches.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Scholarship

log = logging.getLogger("liens")
BROKEN_CODES = {404, 410, 451}
BROWSER_UA = "Mozilla/5.0 (compatible; ScholarFitLinkCheck/1.0)"


def _same_page(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return pa.netloc.removeprefix("www.") == pb.netloc.removeprefix("www.") and pa.path.rstrip("/") == pb.path.rstrip("/")


def check_url(url: str, client: httpx.Client) -> tuple[str, str | None, int | None]:
    """Retourne (statut, adresse finale, code HTTP)."""
    try:
        r = client.head(url)
        if r.status_code in (403, 405, 429, 501) or r.status_code >= 500:
            r = client.get(url)
    except (httpx.ConnectError, httpx.UnsupportedProtocol, httpx.InvalidURL) as e:
        # domaine inexistant ou refus de connexion : le lien est mort
        if "Name or service not known" in str(e) or "nodename nor servname" in str(e) or isinstance(e, httpx.InvalidURL):
            return "casse", None, None
        return "non_verifie", None, None
    except httpx.HTTPError:
        return "non_verifie", None, None
    final = str(r.url)
    if r.status_code in BROKEN_CODES:
        return "casse", final, r.status_code
    if 200 <= r.status_code < 300:
        return ("ok" if _same_page(url, final) else "redirige"), final, r.status_code
    return "non_verifie", final, r.status_code  # 401, 403, 5xx : on ne conclut pas


def check_links(db: Session, max_age_days: int = 7, limit: int | None = None) -> dict[str, int]:
    """Vérifie les liens jamais testés ou testés il y a plus de ``max_age_days`` jours."""
    since = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    counts = {"ok": 0, "redirige": 0, "casse": 0, "non_verifie": 0}
    todo = []
    for s in db.scalars(select(Scholarship)):
        checked = s.link_checked_at
        if checked is not None and checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        if checked is None or checked < since or s.link_status == "non_verifie":
            todo.append(s)
    if limit:
        todo = todo[:limit]
    headers = {"User-Agent": BROWSER_UA, "Accept-Language": "fr,en;q=0.8"}
    with httpx.Client(headers=headers, timeout=15, follow_redirects=True) as client:
        cache: dict[str, tuple[str, str | None, int | None]] = {}
        for s in todo:
            url = s.official_url
            if url not in cache:
                cache[url] = check_url(url, client)
            status, final, code = cache[url]
            s.link_status = status
            s.link_final_url = final
            s.link_checked_at = datetime.now(timezone.utc)
            if status == "casse":
                log.warning("Lien cassé (%s) : %s → %s", code, s.title, url)
            counts[status] += 1
    db.commit()
    return counts


def broken(db: Session) -> list[Scholarship]:
    return list(db.scalars(select(Scholarship).where(Scholarship.link_status == "casse")))


__all__ = ["check_links", "check_url", "broken", "get_settings"]
