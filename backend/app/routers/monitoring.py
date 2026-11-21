"""Administration et supervision : signalements des fiches, journal d'audit, coût de l'IA, erreurs du site."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import ratelimit
from ..alerts import _add
from ..config import get_settings
from ..db import get_db
from ..models import AICost, AuditLog, ScholarshipReport, User
from ..security import admin_user, optional_user
from .community import REPORT_REASONS

router = APIRouter(prefix="/api", tags=["administration et supervision"])
log = logging.getLogger("erreurs-site")

REPORT_STATUSES = {"ouvert", "corrige", "rejete"}


# ---------------------------------------------------------------- signalements
class ReportUpdate(BaseModel):
    status: str = Field(pattern="^(corrige|rejete|ouvert)$")
    note: str | None = Field(default=None, max_length=500)
    all_for_scholarship: bool = False  # traiter d'un coup tous les signalements ouverts de la fiche


def _report_out(r: ScholarshipReport, emails: dict[int, str]) -> dict:
    s = r.scholarship
    return {
        "id": r.id, "reason": r.reason, "reason_label": REPORT_REASONS.get(r.reason, (r.reason,))[0],
        "comment": r.comment, "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None, "resolution_note": r.resolution_note,
        "reporter": emails.get(r.user_id) if r.user_id else None,
        "scholarship": {"id": s.id, "title": s.title, "official_url": s.official_url, "link_status": s.link_status} if s else None,
    }


@router.get("/admin/signalements")
def list_reports(status: str | None = Query("ouvert", pattern="^(ouvert|corrige|rejete|tous)$"),
                 _: User = Depends(admin_user), db: Session = Depends(get_db)):
    stmt = select(ScholarshipReport).order_by(ScholarshipReport.created_at.desc()).limit(300)
    if status and status != "tous":
        stmt = stmt.where(ScholarshipReport.status == status)
    reports = list(db.scalars(stmt))
    ids = {r.user_id for r in reports if r.user_id}
    emails = dict(db.execute(select(User.id, User.email).where(User.id.in_(ids))).all()) if ids else {}
    counts = dict(db.execute(select(ScholarshipReport.scholarship_id, func.count()).where(ScholarshipReport.status == "ouvert")
                             .group_by(ScholarshipReport.scholarship_id)).all())
    out = []
    for r in reports:
        item = _report_out(r, emails)
        item["open_for_scholarship"] = counts.get(r.scholarship_id, 0)
        out.append(item)
    return out


@router.patch("/admin/signalements/{rid}")
def resolve_report(rid: int, body: ReportUpdate, request: Request, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = db.get(ScholarshipReport, rid)
    if not r:
        raise HTTPException(404, "Signalement introuvable")
    targets = [r]
    if body.all_for_scholarship:
        targets = list(db.scalars(select(ScholarshipReport).where(
            ScholarshipReport.scholarship_id == r.scholarship_id, ScholarshipReport.status == "ouvert")))
        if r not in targets:
            targets.append(r)
    now = datetime.now(timezone.utc)
    for x in targets:
        x.status = body.status
        x.resolution_note = (body.note or "").strip() or None
        x.resolved_at = None if body.status == "ouvert" else now
        x.resolved_by_id = None if body.status == "ouvert" else admin.id
        if body.status == "corrige" and x.user_id:
            reporter = db.get(User, x.user_id)
            if reporter is not None:
                title = x.scholarship.title if x.scholarship else ""
                _add(db, reporter, f"signalement-corrige-{x.id}", "signalement",
                     f"Merci ! La fiche « {title} » que vous avez signalée a été corrigée.", x.scholarship_id)
    request.state.audit_details = {"statut": body.status, "nombre": len(targets), "fiche": r.scholarship_id}
    db.commit()
    return {"updated": len(targets)}


# ---------------------------------------------------------------- journal d'audit
@router.get("/admin/audit")
def audit_log(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200), action: str | None = Query(None, max_length=120),
              actor: str | None = Query(None, max_length=320), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * per_page).limit(per_page))
    return {"total": total, "items": [{
        "id": a.id, "created_at": a.created_at.isoformat() if a.created_at else None, "actor": a.actor_email,
        "action": a.action, "target_type": a.target_type, "target_id": a.target_id, "details": a.details or {},
        "ip": a.ip, "status_code": a.status_code,
    } for a in rows]}


# ---------------------------------------------------------------- coût de l'IA
@router.get("/admin/couts-ia")
def ai_costs(days: int = Query(30, ge=1, le=365), _: User = Depends(admin_user), db: Session = Depends(get_db)):
    s = get_settings()
    since = date.today() - timedelta(days=days - 1)
    per_day = db.execute(
        select(AICost.day, func.sum(AICost.cost_usd), func.count(), func.sum(AICost.input_tokens), func.sum(AICost.output_tokens),
               func.sum(AICost.web_searches))
        .where(AICost.day >= since).group_by(AICost.day).order_by(AICost.day)
    ).all()
    per_purpose = db.execute(
        select(AICost.purpose, func.sum(AICost.cost_usd), func.count()).where(AICost.day >= since)
        .group_by(AICost.purpose).order_by(func.sum(AICost.cost_usd).desc())
    ).all()
    today = next((float(c or 0) for d, c, *_ in per_day if d == date.today()), 0.0)
    total = sum(float(c or 0) for _, c, *_ in per_day)
    return {
        "currency": "USD", "ai_enabled": s.ai_enabled, "model": s.claude_model, "daily_budget": s.ai_daily_budget_usd or None,
        "today": round(today, 4), "total": round(total, 4), "average_per_day": round(total / days, 4),
        "days": [{"day": d.isoformat(), "cost": round(float(c or 0), 4), "calls": n, "input_tokens": int(i or 0),
                  "output_tokens": int(o or 0), "web_searches": int(w or 0)} for d, c, n, i, o, w in per_day],
        "by_purpose": [{"purpose": p, "cost": round(float(c or 0), 4), "calls": n} for p, c, n in per_purpose],
        "prices": {"input_per_mtok": s.ai_price_input_per_mtok, "output_per_mtok": s.ai_price_output_per_mtok,
                   "cache_read_per_mtok": s.ai_price_cache_read_per_mtok, "per_web_search": s.ai_price_per_web_search},
    }


# ---------------------------------------------------------------- erreurs du site
class ClientError(BaseModel):
    message: str = Field(max_length=1000)
    stack: str | None = Field(default=None, max_length=4000)
    url: str | None = Field(default=None, max_length=500)
    digest: str | None = Field(default=None, max_length=100)


@router.post("/erreurs-site", status_code=204)
def client_error(body: ClientError, request: Request, user: User | None = Depends(optional_user)):
    """Erreur d'affichage remontée par le navigateur (pages d'erreur du site). Journalisée, et
    envoyée à Sentry si SENTRY_DSN est configuré. Aucune donnée personnelle n'est jointe."""
    try:
        ratelimit.check(f"client-error:{ratelimit.client_ip(request)}", 20, 600)
    except HTTPException:
        return  # trop d'erreurs d'un même visiteur : on ignore sans le signaler
    log.warning("Erreur du site sur %s : %s%s", body.url, body.message, f" (digest {body.digest})" if body.digest else "")
    if get_settings().sentry_dsn:
        try:
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                scope.set_tag("source", "navigateur")
                scope.set_context("page", {"url": body.url, "digest": body.digest, "connecte": user is not None})
                if body.stack:
                    scope.set_extra("stack", body.stack)
                sentry_sdk.capture_message(f"Erreur du site : {body.message}", level="error")
        except Exception:  # noqa: BLE001
            log.exception("Envoi à Sentry impossible")
