"""Pages de référencement : une page par pays d'études et par type d'offre (bourses, stages, conférences).

    /api/seo/destinations          liste des pays avec le nombre d'offres ouvertes par type (plan du site)
    /api/seo/destinations/{slug}   un pays : nom, région, compteurs et offres ouvertes (option kind=)

L'adresse publique est lisible (« /destinations/france/bourses ») ; le slug vient du nom français du pays.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import i18n
from ..db import get_db
from ..deadlines import deadline_info
from ..geo import REGIONS, WORLD
from ..i18n import t
from ..models import Scholarship
from ..serializers import scholarship_out
from ..vocab import COUNTRIES

router = APIRouter(prefix="/api/seo", tags=["référencement"])
REGIONS_EN = {"afrique": "Africa", "europe": "Europe", "amerique": "Americas", "asie": "Asia and the Middle East", "oceanie": "Oceania"}
KIND_SLUGS = {"bourses": "bourse", "stages": "stage", "conferences": "conference"}


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


SLUGS: dict[str, str] = {slugify(name): code for code, name in COUNTRIES.items()}
CODE_SLUG: dict[str, str] = {code: slug for slug, code in SLUGS.items()}


def is_public(s: Scholarship, today: date) -> bool:
    """Offre affichée au public : candidatures ouvertes et lien officiel en état de marche."""
    return s.link_status != "casse" and deadline_info(s, today).status != "expiree"


def _counts(db: Session, today: date) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for s in db.scalars(select(Scholarship)):
        if not is_public(s, today):
            continue
        for c in set(s.study_countries or []):
            row = out.setdefault(c, {"bourse": 0, "stage": 0, "conference": 0})
            row[s.kind or "bourse"] = row.get(s.kind or "bourse", 0) + 1
    return out


@router.get("/destinations")
def destinations(db: Session = Depends(get_db)):
    today = date.today()
    names = i18n.countries(COUNTRIES)
    rows = []
    for code, counts in _counts(db, today).items():
        if code not in CODE_SLUG:
            continue
        region = WORLD.get(code, (None, None))[1]
        rows.append({"code": code, "slug": CODE_SLUG[code], "name": names.get(code, COUNTRIES.get(code, code)),
                     "region": region, "counts": counts, "total": sum(counts.values())})
    rows.sort(key=lambda r: (-r["total"], r["name"]))
    return rows


@router.get("/destinations/{slug}")
def destination(slug: str, kind: str | None = Query(None, pattern="^(bourses|stages|conferences)$"),
                limit: int = Query(60, ge=1, le=200), db: Session = Depends(get_db)):
    code = SLUGS.get(slug.lower())
    if code is None:
        raise HTTPException(404, t("Destination inconnue", "Unknown destination"))
    today = date.today()
    wanted = KIND_SLUGS.get(kind) if kind else None
    items = [s for s in db.scalars(select(Scholarship))
             if code in (s.study_countries or []) and is_public(s, today) and (wanted is None or (s.kind or "bourse") == wanted)]
    counts = {"bourse": 0, "stage": 0, "conference": 0}
    for s in db.scalars(select(Scholarship)):
        if code in (s.study_countries or []) and is_public(s, today):
            counts[s.kind or "bourse"] = counts.get(s.kind or "bourse", 0) + 1
    info = {s.id: deadline_info(s, today) for s in items}
    items.sort(key=lambda s: (not s.full_funding, info[s.id].priority, s.deadline or date.max))
    names = i18n.countries(COUNTRIES)
    region = WORLD.get(code, (None, None))[1]
    full = sum(1 for s in items if s.full_funding)
    return {
        "code": code, "slug": slug.lower(), "name": names.get(code, COUNTRIES[code]), "region": region,
        "region_name": i18n.loc(REGIONS, REGIONS_EN).get(region, region) if region else None,
        "kind": kind, "counts": counts, "total": len(items), "full_funding": full,
        "items": [scholarship_out(s, today) for s in items[:limit]],
    }
