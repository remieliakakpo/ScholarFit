"""Côté membres : signaler une fiche, recherches sauvegardées, désabonnement des e-mails, calendrier.

Les écrans d'administration correspondants (signalements, journal, coûts IA) sont dans
app/routers/monitoring.py.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import ratelimit
from ..alerts import UNSUBSCRIBE, _add
from ..db import get_db
from ..details import content
from ..i18n import t
from ..models import Application, SavedSearch, Scholarship, ScholarshipReport, User
from ..security import current_user, user_from_link
from .scholarships import FILTER_KEYS

router = APIRouter(prefix="/api", tags=["signalements, recherches et calendrier"])

REPORT_REASONS = {
    "lien_mort": ("Le lien officiel ne marche plus", "The official link is broken"),
    "date_fausse": ("La date limite est fausse", "The deadline is wrong"),
    "infos_fausses": ("Montant, conditions ou pièces erronés", "Wrong amount, conditions or documents"),
    "plus_disponible": ("L'offre n'existe plus", "The opportunity no longer exists"),
    "autre": ("Autre problème", "Other problem"),
}
LINK_REPORTS_TO_FLAG = 3  # signalements « lien mort » de personnes différentes avant de marquer le lien cassé
MAX_SAVED_SEARCHES = 20


# ---------------------------------------------------------------- signalements
class ReportIn(BaseModel):
    reason: str = Field(max_length=30)
    comment: str | None = Field(default=None, max_length=1000)


@router.get("/signalements/motifs")
def report_reasons():
    return [{"code": k, "label": t(fr, en)} for k, (fr, en) in REPORT_REASONS.items()]


@router.post("/scholarships/{sid}/signalements", status_code=201)
def report_scholarship(sid: int, body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Un membre signale une erreur sur une fiche. Un seul signalement ouvert par personne et par fiche."""
    ratelimit.check(f"report:{user.id}", 10, 3600)
    if body.reason not in REPORT_REASONS:
        raise HTTPException(422, t("Motif inconnu", "Unknown reason"))
    s = db.get(Scholarship, sid)
    if not s:
        raise HTTPException(404, t("Bourse introuvable", "Scholarship not found"))
    open_ = db.scalars(select(ScholarshipReport).where(
        ScholarshipReport.scholarship_id == sid, ScholarshipReport.user_id == user.id, ScholarshipReport.status == "ouvert",
    )).first()
    if open_:
        raise HTTPException(409, t("Vous avez déjà signalé cette fiche : l'équipe la vérifie.",
                                   "You already reported this listing: the team is checking it."))
    r = ScholarshipReport(scholarship_id=sid, user_id=user.id, reason=body.reason,
                          comment=(body.comment or "").strip() or None)
    db.add(r)
    db.flush()
    if body.reason == "lien_mort":
        reporters = db.scalar(select(func.count(func.distinct(ScholarshipReport.user_id))).where(
            ScholarshipReport.scholarship_id == sid, ScholarshipReport.reason == "lien_mort",
            ScholarshipReport.status == "ouvert",
        ))
        if reporters >= LINK_REPORTS_TO_FLAG:
            s.link_status = "casse"  # apparaît dans « Liens cassés » de l'administration
    for admin in db.scalars(select(User).where(User.is_admin.is_(True))):  # une alerte par fiche et par jour
        _add(db, admin, f"signalement-{sid}-{date.today().isoformat()}", "signalement",
             f"Fiche signalée : « {s.title} » ({REPORT_REASONS[body.reason][0].lower()}).", sid)
    db.commit()
    return {"id": r.id, "message": t("Merci ! L'équipe va vérifier cette fiche.", "Thank you! The team will check this listing.")}


# ---------------------------------------------------------------- recherches sauvegardées
class SavedSearchIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    filters: dict
    alerts_enabled: bool = True

    @field_validator("filters")
    @classmethod
    def _filters(cls, v: dict) -> dict:
        clean = {}
        for k, val in v.items():
            if k not in FILTER_KEYS or val in (None, "", [], {}):
                continue
            if not isinstance(val, (str, int, float, bool)):
                raise ValueError(f"filtre « {k} » invalide")
            clean[k] = val
        if len(json.dumps(clean, ensure_ascii=False)) > 2000:
            raise ValueError("filtres trop longs")
        if not clean:
            raise ValueError("choisissez au moins un filtre")
        return clean


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    alerts_enabled: bool | None = None


def _ss_out(ss: SavedSearch) -> dict:
    return {"id": ss.id, "name": ss.name, "filters": ss.filters, "alerts_enabled": ss.alerts_enabled,
            "created_at": ss.created_at.isoformat() if ss.created_at else None}


def _own_search(sid: int, user: User, db: Session) -> SavedSearch:
    ss = db.get(SavedSearch, sid)
    if not ss or ss.user_id != user.id:
        raise HTTPException(404, t("Recherche introuvable", "Search not found"))
    return ss


@router.get("/recherches")
def list_searches(user: User = Depends(current_user)):
    return [_ss_out(ss) for ss in sorted(user.saved_searches, key=lambda x: x.id, reverse=True)]


@router.post("/recherches", status_code=201)
def save_search(body: SavedSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(user.saved_searches) >= MAX_SAVED_SEARCHES:
        raise HTTPException(409, t(f"{MAX_SAVED_SEARCHES} recherches au plus : supprimez-en une d'abord.",
                                   f"{MAX_SAVED_SEARCHES} searches at most: delete one first."))
    # Seules les fiches ajoutées à partir de maintenant déclencheront une alerte
    ss = SavedSearch(user_id=user.id, name=body.name.strip(), filters=body.filters, alerts_enabled=body.alerts_enabled,
                     last_checked_at=datetime.now(timezone.utc))
    db.add(ss)
    db.commit()
    return _ss_out(ss)


@router.patch("/recherches/{sid}")
def update_search(sid: int, body: SavedSearchUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ss = _own_search(sid, user, db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ss, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return _ss_out(ss)


@router.delete("/recherches/{sid}", status_code=204)
def delete_search(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ss = _own_search(sid, user, db)
    db.delete(ss)
    db.commit()


# ---------------------------------------------------------------- désabonnement
class TokenIn(BaseModel):
    token: str = Field(max_length=2000)


@router.post("/alertes/desabonner")
def unsubscribe(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    """Lien en bas de chaque e-mail d'alerte : coupe les e-mails sans avoir à se connecter."""
    ratelimit.check(f"unsub:{ratelimit.client_ip(request)}", 20, 3600)
    user = user_from_link(db, body.token, UNSUBSCRIBE)
    if user is None:
        raise HTTPException(400, t("Ce lien n'est plus valable. Connectez-vous pour régler vos alertes dans votre profil.",
                                   "This link is no longer valid. Sign in to manage your alerts in your profile."))
    if user.profile is not None:
        user.profile.alerts_opt_in = False
    db.commit()
    return {"message": t("C'est fait : vous ne recevrez plus d'e-mails d'alerte. Vous pouvez les réactiver dans votre profil.",
                         "Done: you will no longer receive alert e-mails. You can turn them back on in your profile.")}


# ---------------------------------------------------------------- calendrier (.ics)
def _ics_text(v: str) -> str:
    return v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Lignes de 75 octets au plus (RFC 5545), suite précédée d'une espace."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > 74:
            out.append(cur.decode("utf-8"))
            cur = b" "
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def _event(s: Scholarship, stamp: str, site: str) -> list[str]:
    from ..mailer import link

    title = content(s, "title")
    d = s.deadline
    url = link(f"/bourses/{s.id}")
    desc = t(f"Date limite de candidature. Fiche ScholarFit : {url} - Site officiel : {s.official_url}",
             f"Application deadline. ScholarFit listing: {url} - Official website: {s.official_url}")
    if s.deadline_estimated:
        desc += t(" (date estimée : à vérifier sur le site officiel)", " (estimated date: check the official website)")
    lines = [
        "BEGIN:VEVENT",
        f"UID:bourse-{s.id}-{d.isoformat()}@{site}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{_ics_text(t('Date limite : ', 'Deadline: ') + title)}",
        f"DESCRIPTION:{_ics_text(desc)}",
        f"URL:{_ics_text(url)}",
        "TRANSP:TRANSPARENT",
    ]
    for days in (7, 1):
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER:-P{days}D",
                  f"DESCRIPTION:{_ics_text(t(f'Dans {days} jour(s) : ', f'In {days} day(s): ') + title)}", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def _calendar(events: list[Scholarship], name: str) -> Response:
    from urllib.parse import urlsplit

    from ..mailer import link

    site = urlsplit(link("/")).hostname or "scholarfit"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ScholarFit//Dates limites//FR", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_ics_text(name)}"]
    for s in events:
        lines += _event(s, stamp, site)
    lines.append("END:VCALENDAR")
    body = "\r\n".join(_fold(x) for x in lines) + "\r\n"
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="scholarfit-dates-limites.ics"'})


@router.get("/scholarships/{sid}/calendrier.ics")
def scholarship_ics(sid: int, db: Session = Depends(get_db)):
    s = db.get(Scholarship, sid)
    if not s or not s.deadline or s.deadline < date.today():
        raise HTTPException(404, t("Pas de date limite à venir pour cette offre", "No upcoming deadline for this opportunity"))
    return _calendar([s], "ScholarFit")


@router.get("/calendrier.ics")
def my_calendar(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Toutes les dates limites des candidatures suivies (pas encore envoyées)."""
    today = date.today()
    apps = db.scalars(select(Application).where(Application.user_id == user.id,
                                                Application.status.in_(("a_preparer", "en_cours"))))
    events = sorted({a.scholarship.id: a.scholarship for a in apps if a.scholarship.deadline and a.scholarship.deadline >= today}.values(),
                    key=lambda s: s.deadline)
    return _calendar(events, t("Mes dates limites ScholarFit", "My ScholarFit deadlines"))
