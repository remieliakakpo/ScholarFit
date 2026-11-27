from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
def delete(sid: int, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = db.get(Scholarship, sid)
    if s:
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
        return {"status": run_source(db, name)}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


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
