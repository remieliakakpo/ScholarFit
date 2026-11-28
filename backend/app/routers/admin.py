from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import run_alerts
from ..coaching import run_reminders
from ..config import get_settings
from ..db import get_db
from ..models import Scholarship, Source, User
from ..schemas import ScholarshipIn, ScholarshipOut, SourceOut
from ..scrapers.base import PoliteFetcher, RobotsDisallowed
from ..scrapers.collector import expire_old, load_source_configs, run_source, slugify, sync_sources, upsert
from ..scrapers.extract import extract
from ..security import admin_user
from ..serializers import scholarship_out

router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.post("/scholarships", response_model=ScholarshipOut, status_code=201)
def create(body: ScholarshipIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Saisie manuelle (équipe ou organisme) : la fiche est considérée comme vérifiée."""
    s, _new = upsert(db, body.model_dump(), source=None, verified=True)
    db.commit()
    return scholarship_out(s)


@router.put("/scholarships/{sid}", response_model=ScholarshipOut)
def update(sid: int, body: ScholarshipIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(Scholarship, sid)
    if not s:
        raise HTTPException(404, "Bourse introuvable")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.edited_by_admin = True  # la fiche de départ ne l'écrasera plus
    s.review = "publie"
    s.slug = slugify(s.title) if not db.scalars(select(Scholarship).where(Scholarship.slug == slugify(s.title), Scholarship.id != sid)).first() else s.slug
    s.verified_at = datetime.now(timezone.utc)
    db.commit()
    return scholarship_out(s)


@router.post("/scholarships/{sid}/verify", response_model=ScholarshipOut)
def verify(sid: int, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(Scholarship, sid)
    if not s:
        raise HTTPException(404, "Bourse introuvable")
    s.status = "active"
    s.deadline_estimated = False  # la date a été confirmée sur le site officiel
    s.edited_by_admin = True
    s.review = "publie"
    s.verified_at = datetime.now(timezone.utc)
    db.commit()
    return scholarship_out(s)


@router.post("/liens/verifier")
def verify_links(limit: int = 40, tout: bool = False, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Teste les liens officiels (40 par appel pour rester rapide ; la collecte automatique fait le reste)."""
    from ..linkcheck import check_links

    return check_links(db, max_age_days=0 if tout else 7, limit=limit)


@router.get("/liens/casses", response_model=list[ScholarshipOut])
def broken_links(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Bourses dont le lien officiel ne répond plus : à corriger (PUT /api/admin/scholarships/{id})."""
    from ..linkcheck import broken

    return [scholarship_out(s) for s in broken(db)]


@router.delete("/scholarships/{sid}", status_code=204)
def delete(sid: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(Scholarship, sid)
    if s:
        request.state.audit_details = {"titre": s.title, "lien": s.official_url}
        db.delete(s)
        db.commit()


@router.get("/sources", response_model=list[SourceOut])
def sources(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    sync_sources(db)
    db.commit()
    return list(db.scalars(select(Source).order_by(Source.name)))


@router.get("/sources/config")
def sources_config(_: User = Depends(admin_user)):
    return load_source_configs()


@router.post("/sources/{name}/run")
def run(name: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    try:
        status = run_source(db, name)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    from ..ai.batch import submit_pending

    sent = submit_pending(db)  # lancé à la main : on n'attend pas le prochain passage pour envoyer le lot
    return {"status": status, "lot_envoye": sent}


class ExtractIn(BaseModel):
    url: str
    save: bool = False


@router.post("/extract")
def extract_url(body: ExtractIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Teste l'extraction sur une page (robots.txt respecté). save=true l'ajoute « à vérifier »."""
    fetcher = PoliteFetcher(min_delay=0)
    try:
        html = fetcher.get(body.url)
    except RobotsDisallowed as e:
        raise HTTPException(403, "robots.txt interdit la collecte de cette page") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Page injoignable : {e}") from e
    finally:
        fetcher.close()
    record = extract(html, body.url, use_ai=get_settings().ai_enabled)
    if record is None:
        return {"is_scholarship": False}
    if body.save:
        record["organization"] = record.get("organization") or "À compléter"
        s, _new = upsert(db, record, source=None)
        db.commit()
        return {"is_scholarship": True, "saved_id": s.id, "record": record}
    return {"is_scholarship": True, "record": record}


@router.post("/maintenance")
def maintenance(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Expirations, alertes et rappels (la collecte automatique le fait aussi chaque jour)."""
    expired = expire_old(db)
    alerts = run_alerts(db)
    reminders = run_reminders(db)
    return {"bourses_mises_a_jour": expired, "alertes_creees": alerts, "rappels_accompagnement": reminders}


# ---------------------------------------------------------------- types d'opportunités affichés
class KindsIn(BaseModel):
    kinds_enabled: list[str] = Field(max_length=20)


@router.get("/types")
def opportunity_types(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Tous les types, avec leur état (affiché ou non) et le nombre d'offres en base."""
    from .. import i18n
    from ..deadlines import deadline_info
    from ..site_settings import enabled_kinds
    from ..vocab import KINDS

    shown = enabled_kinds(db)
    today = datetime.now(timezone.utc).date()
    counts = {k: [0, 0] for k in KINDS}
    for s in db.scalars(select(Scholarship)):
        row = counts.setdefault(s.kind or "bourse", [0, 0])
        row[0] += 1
        row[1] += deadline_info(s, today).status != "expiree"
    labels = i18n.loc(KINDS, i18n.KINDS_EN)
    return [{"kind": k, "label": labels[k], "enabled": k in shown, "total": counts[k][0], "open": counts[k][1]} for k in KINDS]


@router.put("/types")
def set_opportunity_types(body: KindsIn, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Choisit les types affichés sur le site (et collectés). Au moins un doit rester."""
    from ..site_settings import enabled_kinds, set_enabled_kinds
    from ..vocab import KINDS

    unknown = [k for k in body.kinds_enabled if k not in KINDS]
    if unknown:
        raise HTTPException(422, f"Types inconnus : {unknown}")
    before = enabled_kinds(db)
    try:
        after = set_enabled_kinds(db, body.kinds_enabled)
    except ValueError as e:
        raise HTTPException(422, "Gardez au moins un type affiché") from e
    request.state.audit_details = {"avant": before, "apres": after}  # journal d'audit
    return {"kinds_enabled": after}
