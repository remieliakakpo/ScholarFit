from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select  # noqa: F401
from sqlalchemy.orm import Session

from ..db import get_db
from ..i18n import is_en, t
from ..models import Scholarship
from ..schemas import ScholarshipOut, ScholarshipPage
from ..serializers import scholarship_out
from ..deadlines import deadline_info
from ..details import REQUIREMENTS
from ..geo import REGIONS, WORLD, countries_in
from ..vocab import COUNTRIES, DOMAINS, KIND_PATTERN, KINDS, LEVELS, NATIONALITY_GROUPS, expand_nationalities

router = APIRouter(prefix="/api", tags=["bourses"])


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    from ..site_settings import enabled_kinds

    shown = enabled_kinds(db)
    """Listes contrôlées pour les formulaires du site."""
    from .. import i18n
    from ..details import COVERAGE_LABELS, requirement_label

    countries = i18n.countries(COUNTRIES)
    return {
        "lang": i18n.lang(),
        "levels": i18n.loc(LEVELS, i18n.LEVELS_EN),
        "domains": i18n.loc(DOMAINS, i18n.DOMAINS_EN),
        "countries": dict(sorted(countries.items(), key=lambda kv: kv[1])),
        "nationality_groups": {k: sorted(v) for k, v in NATIONALITY_GROUPS.items()},
        "regions": i18n.loc(REGIONS, i18n.REGIONS_EN),
        "kinds": {k: v for k, v in i18n.loc(KINDS, i18n.KINDS_EN).items() if k in shown},  # types affichés
        "country_regions": {c: w[1] for c, w in WORLD.items()},
        "deadline_statuses": i18n.loc({"urgente": "Urgent (14 jours ou moins)", "bientot": "Bientôt (45 jours ou moins)",
                                       "ouverte": "Ouverte", "inconnue": "Date non publiée", "expiree": "Expirée"},
                                      i18n.DEADLINE_STATUSES_EN),
        "statuses": i18n.loc({"a_preparer": "À préparer", "en_cours": "En cours", "envoyee": "Envoyée", "acceptee": "Acceptée",
                              "refusee": "Refusée"}, i18n.APPLICATION_STATUSES_EN),
        "coverage": i18n.loc(COVERAGE_LABELS, i18n.COVERAGE_EN),
        "requirements": {code: requirement_label(code)[0] for code in REQUIREMENTS},
    }


# Paramètres du catalogue qu'une recherche sauvegardée peut retenir (mêmes noms que GET /api/scholarships)
FILTER_KEYS = ("q", "kind", "level", "country", "country_exact", "domain", "nationality", "full_funding",
               "deadline_after", "deadline_before", "include_expired", "region", "deadline_status")


def search(db: Session, *, today: date | None = None, q: str | None = None, kind: str | None = None,
           level: str | None = None, country: str | None = None, country_exact: bool = False, domain: str | None = None,
           nationality: str | None = None, full_funding: bool | None = None, deadline_after: date | None = None,
           deadline_before: date | None = None, include_expired: bool = False, region: str | None = None,
           deadline_status: str | None = None, extra_where=None, enabled: list[str] | None = None):
    """Fiches qui répondent aux filtres du catalogue (sans tri ni pagination) et leur état de date limite.
    ``enabled`` : types affichés (réglage de l'administration) ; les autres sont exclus."""
    today = today or date.today()
    if enabled is not None and kind and kind not in enabled:
        return [], {}
    stmt = select(Scholarship).where(Scholarship.review == "publie")
    if enabled is not None and not kind:
        stmt = stmt.where(Scholarship.kind.in_(enabled))
    if extra_where is not None:
        stmt = stmt.where(extra_where)
    if kind:
        stmt = stmt.where(Scholarship.kind == kind)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Scholarship.title).like(like), func.lower(Scholarship.organization).like(like), func.lower(Scholarship.summary).like(like)))
    if full_funding is not None:
        stmt = stmt.where(Scholarship.full_funding == full_funding)
    if deadline_after:
        stmt = stmt.where(Scholarship.deadline >= deadline_after)
    if deadline_before:
        stmt = stmt.where(Scholarship.deadline <= deadline_before)

    items = list(db.scalars(stmt))
    info = {s.id: deadline_info(s, today) for s in items}
    wanted = set(deadline_status.split(",")) if deadline_status else None
    if wanted:
        items = [s for s in items if info[s.id].status in wanted]
    elif not include_expired:
        items = [s for s in items if info[s.id].status != "expiree"]
    # Lien officiel mort (404, domaine disparu) : l'offre est retirée du site jusqu'à sa correction dans /admin
    items = [s for s in items if s.link_status != "casse"]
    if region:
        zone = countries_in(region)
        items = [s for s in items if set(s.study_countries or []) & zone]
    # Filtres sur les listes JSON : faits en Python pour rester compatibles SQLite et PostgreSQL.
    # (Pour un gros catalogue : index GIN PostgreSQL sur ces colonnes.)
    if level:
        items = [s for s in items if not s.levels or level in s.levels]
    if country:
        if country_exact:  # seulement les offres de ce pays (même total que /api/stats/countries)
            items = [s for s in items if country in (s.study_countries or [])]
        else:  # inclut les offres multi-pays, ouvertes partout
            items = [s for s in items if not s.study_countries or country in s.study_countries]
    if domain:
        items = [s for s in items if domain in s.domains or "tous" in s.domains]
    if nationality:
        def ok(s: Scholarship) -> bool:
            allowed = expand_nationalities(s.eligible_nationalities)
            excluded = expand_nationalities(s.excluded_nationalities) if s.excluded_nationalities else set()
            return (allowed is None or nationality in allowed) and nationality not in (excluded or set())
        items = [s for s in items if ok(s)]

    return items, info


@router.get("/scholarships", response_model=ScholarshipPage)
def list_scholarships(
    q: str | None = None,
    kind: str | None = Query(None, pattern=KIND_PATTERN, description="type d'opportunité ; vide = tout"),
    level: str | None = None,
    country: str | None = None,
    country_exact: bool = False,
    domain: str | None = None,
    nationality: str | None = None,
    full_funding: bool | None = None,
    deadline_after: date | None = None,
    deadline_before: date | None = None,
    include_expired: bool = False,
    region: str | None = Query(None, pattern="^(afrique|europe|amerique|asie|oceanie)$"),
    deadline_status: str | None = Query(None, description="un ou plusieurs états séparés par des virgules : urgente,bientot,ouverte,inconnue,expiree"),
    sort: str = Query("deadline", pattern="^(deadline|amount|title|recent|priority)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    today = date.today()
    from ..site_settings import enabled_kinds

    items, info = search(
        db, today=today, enabled=enabled_kinds(db), q=q, kind=kind, level=level, country=country, country_exact=country_exact, domain=domain,
        nationality=nationality, full_funding=full_funding, deadline_after=deadline_after,
        deadline_before=deadline_before, include_expired=include_expired, region=region, deadline_status=deadline_status,
    )

    keys = {
        "deadline": lambda s: (s.deadline is None, s.deadline or date.max),
        "amount": lambda s: (not s.full_funding, -(s.amount or 0)),
        "title": lambda s: s.title.lower(),
        "recent": lambda s: -s.collected_at.timestamp(),
        # urgentes d'abord, puis par date ; les expirées en dernier
        "priority": lambda s: (info[s.id].priority, s.deadline or date.max),
    }
    items.sort(key=keys[sort])
    total = len(items)
    start = (page - 1) * per_page
    return ScholarshipPage(total=total, items=[scholarship_out(s, today) for s in items[start: start + per_page]])


@router.get("/stats/countries")
def stats_countries(include_expired: bool = False, kind: str | None = Query(None, pattern=KIND_PATTERN),
                    db: Session = Depends(get_db)):
    """Nombre réel de bourses par pays d'études (une bourse multi-pays compte dans chacun de ses pays).
    Les bourses sans pays fixe (ex. Erasmus Mundus, AUF) sont comptées à part dans /api/stats."""
    from ..site_settings import enabled_kinds

    today = date.today()
    counts: dict[str, list[int]] = {}
    shown = enabled_kinds(db)
    if kind and kind not in shown:
        return []
    stmt = select(Scholarship).where(Scholarship.kind == kind) if kind else select(Scholarship).where(Scholarship.kind.in_(shown))
    for s in db.scalars(stmt):
        if s.link_status == "casse":
            continue
        open_ = deadline_info(s, today).status != "expiree"
        if not include_expired and not open_:
            continue
        for c in set(s.study_countries or []):
            row = counts.setdefault(c, [0, 0])
            row[0] += 1
            row[1] += open_
    from .. import i18n

    names = i18n.countries(COUNTRIES)
    out = []
    for code, (count, open_count) in counts.items():
        _n, region, lat, lon = WORLD.get(code, (COUNTRIES.get(code, code), None, None, None))
        name = names.get(code, _n)
        out.append({"code": code, "name": name, "region": region, "count": count, "open_count": open_count, "lat": lat, "lon": lon})
    out.sort(key=lambda r: (-r["count"], r["name"]))
    return out


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Chiffres pour la page d'accueil (tout est calculé sur la base, rien n'est en dur)."""
    today = date.today()
    total = open_ = soon = expired = multi = 0
    by_region = {r: 0 for r in REGIONS}
    from ..site_settings import enabled_kinds

    shown = enabled_kinds(db)
    by_kind = {k: 0 for k in KINDS if k in shown}
    countries: set[str] = set()
    for s in db.scalars(select(Scholarship).where(Scholarship.kind.in_(shown))):
        st = deadline_info(s, today).status
        total += 1
        if st == "expiree":
            expired += 1
            continue
        open_ += 1
        by_kind[s.kind or "bourse"] = by_kind.get(s.kind or "bourse", 0) + 1
        soon += st in ("urgente", "bientot")
        if not s.study_countries:
            multi += 1
        countries |= set(s.study_countries or [])
        for r in {WORLD[c][1] for c in s.study_countries or [] if c in WORLD}:
            by_region[r] += 1
    last = db.scalar(select(func.max(Scholarship.collected_at)))
    return {"total": total, "open": open_, "closing_soon": soon, "expired": expired, "countries": len(countries),
            "multi_country": multi, "by_region": by_region, "by_kind": by_kind, "last_collected_at": last}


@router.get("/scholarships/{key}", response_model=ScholarshipOut)
def get_scholarship(key: str, db: Session = Depends(get_db)):
    s = db.get(Scholarship, int(key)) if key.isdigit() else db.scalars(select(Scholarship).where(Scholarship.slug == key)).first()
    from ..site_settings import enabled_kinds

    if not s or (s.kind or "bourse") not in enabled_kinds(db):
        raise HTTPException(404, t("Bourse introuvable", "Scholarship not found"))
    if is_en():
        from ..translate import ensure_en

        ensure_en(db, s)
    return scholarship_out(s)
