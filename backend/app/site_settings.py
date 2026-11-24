"""Réglages du site modifiables depuis l'administration.

``kinds_enabled`` : types d'opportunités affichés aux visiteurs (onglets d'Explorer, recherche, fiches,
matching, alertes). Un type désactivé reste en base mais n'est plus affiché, et sa collecte par
catégorie ou par la découverte n'est pas faite (aucun coût d'IA pour lui). Par défaut : tous.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SiteSetting
from .vocab import KINDS

KINDS_KEY = "kinds_enabled"
_cache: dict[str, tuple[float, object]] = {}
TTL = 30  # secondes


def enabled_kinds(db: Session) -> list[str]:
    hit = _cache.get(KINDS_KEY)
    if hit and hit[0] > time.monotonic():
        return list(hit[1])  # type: ignore[arg-type]
    row = db.scalars(select(SiteSetting).where(SiteSetting.key == KINDS_KEY)).first()
    kinds = [k for k in (row.value or {}).get("kinds", []) if k in KINDS] if row else list(KINDS)
    kinds = kinds or ["bourse"]
    _cache[KINDS_KEY] = (time.monotonic() + TTL, kinds)
    return list(kinds)


def set_enabled_kinds(db: Session, kinds: list[str]) -> list[str]:
    clean = [k for k in KINDS if k in set(kinds)]  # ordre de vocab.KINDS
    if not clean:
        raise ValueError("au moins un type doit rester affiché")
    row = db.scalars(select(SiteSetting).where(SiteSetting.key == KINDS_KEY)).first()
    if row is None:
        row = SiteSetting(key=KINDS_KEY)
        db.add(row)
    row.value = {"kinds": clean}
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    _cache.pop(KINDS_KEY, None)
    return clean


def clear_cache() -> None:
    _cache.clear()
