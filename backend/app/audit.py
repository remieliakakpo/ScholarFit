"""Journal d'audit.

- `record` : une ligne explicite (sécurité des comptes, détails d'une action d'administration).
- `record_admin_request` : appelé par le middleware de app/main.py pour **toute** requête réussie qui
  modifie quelque chose sous /api/admin, pour qu'aucune action d'administration ne passe inaperçue,
  même sur une route ajoutée plus tard.
"""
from __future__ import annotations

import logging
import re

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog, User

log = logging.getLogger("audit")
_ID = re.compile(r"/(\d+)(?=/|$)")


def record(db: Session, actor: User | None, action: str, *, target_type: str | None = None,
           target_id: object = None, details: dict | None = None, request: Request | None = None,
           status_code: int | None = None) -> None:
    """Ajoute une ligne au journal (validée avec la transaction de l'appelant)."""
    ip = None
    if request is not None:
        from .ratelimit import client_ip

        ip = client_ip(request)
    db.add(AuditLog(
        actor_id=actor.id if actor else None, actor_email=actor.email if actor else None, action=action[:120],
        target_type=target_type, target_id=None if target_id is None else str(target_id)[:60],
        details=details or {}, ip=ip, status_code=status_code,
    ))


def admin_action(method: str, path: str) -> tuple[str, str | None, str | None]:
    """« POST /api/admin/scholarships/12/verify » → (action, type de cible, identifiant)."""
    rest = path.removeprefix("/api/admin/").strip("/")
    target_id = None
    m = _ID.search("/" + rest)
    if m:
        target_id = m.group(1)
    template = _ID.sub("/{id}", "/" + rest).lstrip("/")
    target_type = rest.split("/", 1)[0] if rest else None
    return f"{method} {template}", target_type, target_id


def record_admin_request(request: Request, status_code: int, user_id: int | None) -> None:
    from .db import SessionLocal

    action, target_type, target_id = admin_action(request.method, request.url.path)
    db = SessionLocal()
    try:
        actor = db.get(User, user_id) if user_id else None
        details = dict(getattr(request.state, "audit_details", None) or {})  # posés par la route, si utile
        if request.url.query:
            details["query"] = str(request.url.query)
        record(db, actor, action, target_type=target_type, target_id=target_id, request=request,
               status_code=status_code, details=details)
        db.commit()
    except Exception:  # noqa: BLE001 - le journal ne doit jamais faire échouer l'action
        log.exception("Journal d'audit non écrit pour %s", action)
    finally:
        db.close()
