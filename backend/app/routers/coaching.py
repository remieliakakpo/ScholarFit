"""Accompagnement des candidatures : côté candidat, côté conseiller et côté administration."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import coaching as svc
from .. import offers
from ..config import get_settings
from ..db import get_db
from ..i18n import t
from ..matching import profile_completeness
from ..models import Advisor, Coaching, CoachingFile, CoachingMeeting, CoachingMessage, CoachingStep, User
from ..schemas import (
    AdminCoachingOut, AdvisorAdminOut, AdvisorIn, AdvisorPublic, AdvisorUpdate, AssignIn, CloseIn,
    CoachingDetailOut, CoachingFileOut, CoachingOut, CoachingRequestIn, FeedbackIn, MeetingIn, MeetingOut, MeetingUpdate,
    MessageIn, MessageOut, PaymentIn, StepIn, StepOut, StepUpdate, StudentSummary,
)
from ..security import admin_user, current_user
from .applications import app_out

router = APIRouter(prefix="/api/accompagnement", tags=["accompagnement"])
PAYMENT_STATUSES = {"a_payer": "À payer", "paye": "Payé", "offert": "Offert", "rembourse": "Remboursé"}
admin_router = APIRouter(prefix="/api/admin", tags=["administration"])


# ---------- Outils ----------
def _role(c: Coaching, user: User) -> str | None:
    if c.student_id == user.id:
        return "candidat"
    if user.advisor is not None and c.advisor_id == user.advisor.id:
        return "conseiller"
    if user.is_admin:
        return "admin"
    return None


def _get(cid: int, user: User, db: Session) -> tuple[Coaching, str]:
    c = db.get(Coaching, cid)
    role = _role(c, user) if c else None
    if not c or not role:
        raise HTTPException(404, t("Accompagnement introuvable", "Coaching not found"))
    return c, role


def _require(role: str, allowed: tuple[str, ...], what: str) -> None:
    if role not in allowed:
        raise HTTPException(403, t(f"Seul {what} peut faire cela", "You are not allowed to do this"))


def _require_open(c: Coaching) -> None:
    if c.status not in svc.ACTIVE:
        raise HTTPException(409, t("Cet accompagnement est clos", "This coaching is closed"))


def _unread(c: Coaching, role: str) -> int:
    if role == "candidat":
        return sum(1 for m in c.messages if m.author_role != "candidat" and not m.read_by_student)
    return sum(1 for m in c.messages if m.author_role == "candidat" and not m.read_by_advisor)


def _student_name(c: Coaching) -> str:
    p = c.student.profile
    return p.full_name if p is not None and p.full_name else c.student.email.split("@")[0]


def _offer_name(code: str | None) -> str:
    return next((o["name"] for o in offers.catalog() if o["code"] == code), code or "")


def _out(c: Coaching, role: str, cls=CoachingOut, **extra):
    steps = c.steps
    done = sum(1 for s in steps if s.done)
    nxt = next((s for s in sorted(steps, key=lambda s: (s.due_date is None, s.due_date, s.position)) if not s.done), None)
    meeting = svc.next_meeting(c)
    return cls(
        id=c.id, status=c.status, goal=c.goal, needs=c.needs or [], application_ids=c.application_ids or [],
        preferred_language=c.preferred_language, availability=c.availability, share_consent=c.share_consent,
        offer=c.offer or "standard", offer_name=_offer_name(c.offer), price=c.price or 0,
        price_label=offers.price_label(c.price or 0), payment_status=c.payment_status or "a_payer",
        rating=c.rating, feedback=c.feedback, created_at=c.created_at, assigned_at=c.assigned_at, closed_at=c.closed_at,
        advisor=AdvisorPublic.model_validate(c.advisor) if c.advisor else None, student_name=_student_name(c),
        progress=round(100 * done / len(steps)) if steps else 0,
        next_step=StepOut.model_validate(nxt) if nxt else None,
        next_meeting=MeetingOut.model_validate(meeting) if meeting else None,
        unread=_unread(c, role), my_role=role, **extra,
    )


def _advisor_out(db: Session, a: Advisor) -> AdvisorAdminOut:
    return AdvisorAdminOut(
        id=a.id, display_name=a.display_name, bio=a.bio, levels=a.levels or [], countries=a.countries or [],
        domains=a.domains or [], languages=a.languages or [], email=a.user.email, capacity=a.capacity,
        active=a.active, load=svc.load(db, a),
    )


def _other_party(c: Coaching, role: str) -> User | None:
    if role == "candidat":
        return c.advisor.user if c.advisor else None
    return c.student


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    for u in db.scalars(select(User).where(User.id.in_(ids))) if ids else []:
        if u.advisor is not None:
            names[u.id] = u.advisor.display_name
        elif u.profile is not None and u.profile.full_name:
            names[u.id] = u.profile.full_name
        else:
            names[u.id] = "Équipe ScholarFit" if u.is_admin else u.email.split("@")[0]
    return names


# ---------- Candidat ----------
@router.get("/meta")
def meta():
    return {"statuses": svc.STATUSES, "needs": svc.NEEDS, "meeting_modes": svc.MEETING_MODES, "meeting_statuses": svc.MEETING_STATUSES,
            "offers": offers.catalog(), "payment_statuses": PAYMENT_STATUSES}


@router.get("", response_model=list[CoachingOut])
def my_coachings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cs = db.scalars(select(Coaching).where(Coaching.student_id == user.id).order_by(Coaching.created_at.desc()))
    return [_out(c, "candidat") for c in cs]


@router.post("", response_model=CoachingOut, status_code=201)
def request_coaching(body: CoachingRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Demande d'accompagnement. Un seul accompagnement ouvert à la fois."""
    if not body.share_consent:
        raise HTTPException(422, t("Votre accord est nécessaire : le conseiller doit voir votre profil, votre CV et vos candidatures pour vous aider.", "Your consent is needed: the adviser must see your profile, CV and applications to help you."))
    if db.scalars(select(Coaching).where(Coaching.student_id == user.id, Coaching.status.in_(svc.ACTIVE))).first():
        raise HTTPException(409, t("Vous avez déjà un accompagnement en cours", "You already have coaching in progress"))
    unknown = [n for n in body.needs if n not in svc.NEEDS]
    if unknown:
        raise HTTPException(422, t(f"Besoins inconnus : {unknown}", f"Unknown needs: {unknown}"))
    mine = {a.id for a in user.applications}
    if set(body.application_ids) - mine:
        raise HTTPException(422, t("Certaines candidatures ne sont pas dans votre suivi", "Some applications are not in your tracker"))
    offer = offers.paid_offer(body.offer)
    if offer is None:
        raise HTTPException(422, t("Offre inconnue : choisissez standard ou premium (ou postulez seul, sans accompagnement)", "Unknown offer: choose standard or premium (or apply on your own, without coaching)"))
    if offer["max_scholarships"] and len(body.application_ids) > offer["max_scholarships"]:
        n = offer["max_scholarships"]
        raise HTTPException(422, t(f"L'offre {offer['name']} couvre {n} bourse{'s' if n > 1 else ''}. Choisissez l'offre Premium ou retirez des candidatures.",
                                   f"The {offer['name']} offer covers {n} scholarship{'s' if n > 1 else ''}. Choose Premium or remove some applications."))
    c = Coaching(student_id=user.id, goal=body.goal.strip(), needs=body.needs, application_ids=body.application_ids,
                 preferred_language=body.preferred_language, availability=body.availability, share_consent=True,
                 offer=offer["code"], price=offer["price"], currency="XOF", payment_status="a_payer")
    db.add(c)
    db.flush()
    db.refresh(c)
    if get_settings().coaching_auto_assign:
        best = svc.suggest_advisors(db, c, limit=1)
        if best:
            svc.assign(db, c, best[0][0])
    if c.status == "demande":
        for admin in db.scalars(select(User).where(User.is_admin.is_(True))):
            svc.notify(db, admin, f"acc-{c.id}-demande", f"Nouvelle demande d'accompagnement de {_student_name(c)} : à attribuer dans l'administration.")
    db.commit()
    return _out(c, "candidat")


@router.get("/conseiller", response_model=list[CoachingOut])
def advisor_coachings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Espace conseiller : les candidats suivis, les plus récents d'abord."""
    if user.advisor is None:
        raise HTTPException(403, t("Réservé aux conseillers", "Advisers only"))
    cs = db.scalars(select(Coaching).where(Coaching.advisor_id == user.advisor.id).order_by(Coaching.updated_at.desc()))
    return [_out(c, "conseiller") for c in cs]


@router.get("/{cid}", response_model=CoachingDetailOut)
def detail(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    for m in c.messages:
        if role == "candidat":
            m.read_by_student = True
        elif role == "conseiller":
            m.read_by_advisor = True
    db.commit()
    names = _names(db, {m.author_id for m in c.messages if m.author_id})
    messages = [
        MessageOut(id=m.id, author_role=m.author_role, author_name=names.get(m.author_id) if m.author_id else None,
                   content=m.content, application_id=m.application_id, created_at=m.created_at, mine=m.author_id == user.id)
        for m in c.messages
    ]
    student = None
    if role != "candidat" and c.share_consent:
        p = c.student.profile
        student = StudentSummary(email=c.student.email, full_name=p.full_name if p else None)
        if p is not None:
            student = StudentSummary(
                email=c.student.email, full_name=p.full_name, nationalities=p.nationalities or [],
                residence_country=p.residence_country, current_level=p.current_level, target_level=p.target_level,
                domain=p.domain, institution=p.institution, grade_average=p.grade_average,
                wished_countries=p.wished_countries or [], languages=p.languages or {},
                language_scores=p.language_scores or {}, project=p.project, experiences=p.experiences,
                cv_text=p.cv_text, completeness=profile_completeness(p)[0],
            )
    apps = [app_out(a) for a in svc.linked_applications(c)] if (role == "candidat" or c.share_consent) else []
    return _out(
        c, role, CoachingDetailOut,
        steps=[StepOut.model_validate(s) for s in c.steps], messages=messages,
        meetings=[MeetingOut.model_validate(m) for m in c.meetings], student=student, applications=apps,
        files=[_file_out(f, user) for f in _files(db, c)],
    )


# ---------- Documents échangés ----------
FILE_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
FILE_MAX = 8 * 1024 * 1024
FILE_CATEGORIES = ("livrable", "piece", "preuve_depot")


def _files(db: Session, c: Coaching) -> list[CoachingFile]:
    return list(db.scalars(select(CoachingFile).where(CoachingFile.coaching_id == c.id).order_by(CoachingFile.created_at.desc())))


def _file_out(f: CoachingFile, user: User) -> CoachingFileOut:
    return CoachingFileOut(id=f.id, author_role=f.author_role, category=f.category, filename=f.filename,
                           content_type=f.content_type, size=f.size, note=f.note, created_at=f.created_at,
                           mine=f.author_id == user.id)


@router.post("/{cid}/fichiers", response_model=CoachingFileOut, status_code=201)
async def upload_file(cid: int, file: UploadFile = File(...), category: str = Form("piece"), note: str = Form(""),
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Le candidat envoie une pièce ; l'expert livre un document ou la preuve de dépôt (PDF, Word, image, 8 Mo au plus)."""
    c, role = _get(cid, user, db)
    _require_open(c)
    if category not in FILE_CATEGORIES:
        raise HTTPException(422, t("Type de document inconnu", "Unknown document type"))
    if category in ("livrable", "preuve_depot") and role == "candidat":
        raise HTTPException(403, t("Seul l'expert livre les documents finaux.", "Only the expert can deliver final documents."))
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype not in FILE_TYPES:
        raise HTTPException(415, t("Formats acceptés : PDF, Word, JPG ou PNG.", "Accepted formats: PDF, Word, JPG or PNG."))
    data = await file.read(FILE_MAX + 1)
    if len(data) > FILE_MAX:
        raise HTTPException(413, t("Le fichier dépasse 8 Mo.", "The file is larger than 8 MB."))
    if not data:
        raise HTTPException(422, t("Le fichier est vide.", "The file is empty."))
    name = "".join(ch for ch in (file.filename or "document") if ch.isalnum() or ch in " ._-()").strip()[:150] or "document"
    if not name.lower().endswith(FILE_TYPES[ctype]) and not (ctype == "image/jpeg" and name.lower().endswith(".jpeg")):
        name += FILE_TYPES[ctype]
    f = CoachingFile(coaching_id=c.id, author_id=user.id, author_role=role, category=category, filename=name,
                     content_type=ctype, size=len(data), data=data, note=note.strip()[:300] or None)
    db.add(f)
    db.flush()
    other = _other_party(c, role)
    if other is not None:
        label = {"livrable": "Nouveau document livré par votre expert", "preuve_depot": "Votre candidature a été déposée : la preuve de dépôt est disponible",
                 "piece": f"{_student_name(c)} a envoyé une pièce"}[category]
        svc.notify(db, other, f"acc-fichier-{f.id}", f"{label} : {name}.")
    db.commit()
    return _file_out(f, user)


@router.get("/{cid}/fichiers/{fid}")
def download_file(cid: int, fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, _role = _get(cid, user, db)
    f = db.get(CoachingFile, fid)
    if f is None or f.coaching_id != c.id:
        raise HTTPException(404, t("Document introuvable", "Document not found"))
    safe = f.filename.replace('"', "")
    return Response(f.data, media_type=f.content_type, headers={"Content-Disposition": f'attachment; filename="{safe}"'})


@router.delete("/{cid}/fichiers/{fid}", status_code=204)
def delete_file(cid: int, fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    f = db.get(CoachingFile, fid)
    if f is None or f.coaching_id != c.id:
        raise HTTPException(404, t("Document introuvable", "Document not found"))
    if f.author_id != user.id and role != "admin":
        raise HTTPException(403, t("Vous ne pouvez supprimer que vos propres documents.", "You can only delete your own documents."))
    db.delete(f)
    db.commit()


@router.post("/{cid}/annuler", response_model=CoachingOut)
def cancel(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    _require(role, ("candidat", "admin"), "le candidat")
    _require_open(c)
    c.status = "annule"
    c.closed_at = datetime.now(timezone.utc)
    if c.advisor:
        svc.notify(db, c.advisor.user, f"acc-{c.id}-annule", f"{_student_name(c)} a mis fin à son accompagnement.")
    db.commit()
    return _out(c, role)


@router.post("/{cid}/terminer", response_model=CoachingOut)
def finish(cid: int, body: CloseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    _require(role, ("conseiller", "admin"), "le conseiller")
    if c.status != "en_cours":
        raise HTTPException(409, t("Seul un accompagnement en cours peut être terminé", "Only coaching in progress can be completed"))
    if body.note and body.note.strip():
        db.add(CoachingMessage(coaching_id=c.id, author_id=user.id, author_role=role, content=body.note.strip(), read_by_advisor=True))
    c.status = "termine"
    c.closed_at = datetime.now(timezone.utc)
    svc.notify(db, c.student, f"acc-{c.id}-termine", "Votre accompagnement est terminé. Dites-nous ce que vous en avez pensé !")
    db.commit()
    db.refresh(c)
    return _out(c, role)


@router.post("/{cid}/avis", response_model=CoachingOut)
def give_feedback(cid: int, body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    _require(role, ("candidat",), "le candidat")
    if c.status != "termine":
        raise HTTPException(409, t("L'avis se donne à la fin de l'accompagnement", "Feedback is given at the end of the coaching"))
    c.rating, c.feedback = body.rating, body.feedback
    db.commit()
    return _out(c, role)


# ---------- Étapes ----------
def _step(sid: int, user: User, db: Session) -> tuple[CoachingStep, str]:
    s = db.get(CoachingStep, sid)
    if not s:
        raise HTTPException(404, t("Étape introuvable", "Step not found"))
    _c, role = _get(s.coaching_id, user, db)
    return s, role


@router.post("/{cid}/etapes", response_model=StepOut, status_code=201)
def add_step(cid: int, body: StepIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    _require_open(c)
    if body.application_id is not None and body.application_id not in {a.id for a in c.student.applications}:
        raise HTTPException(422, t("Candidature inconnue", "Unknown application"))
    s = CoachingStep(coaching_id=c.id, position=max((x.position for x in c.steps), default=-1) + 1, **body.model_dump())
    db.add(s)
    if role != "candidat":
        svc.notify(db, c.student, f"acc-etape-{c.id}-{s.position}-ajout", f"Nouvelle étape dans votre accompagnement : « {s.title} ».")
    db.commit()
    return s


@router.patch("/etapes/{sid}", response_model=StepOut)
def update_step(sid: int, body: StepUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s, role = _step(sid, user, db)
    _require_open(s.coaching)
    data = body.model_dump(exclude_unset=True)
    if role == "candidat" and set(data) - {"done"}:
        raise HTTPException(403, t("Vous pouvez cocher une étape ; votre conseiller la modifie", "You can tick a step; your adviser edits it"))
    if "done" in data:
        s.done_at = datetime.now(timezone.utc) if data["done"] else None
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    return s


@router.delete("/etapes/{sid}", status_code=204)
def delete_step(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s, role = _step(sid, user, db)
    _require(role, ("conseiller", "admin"), "le conseiller")
    db.delete(s)
    db.commit()


# ---------- Messages ----------
@router.post("/{cid}/messages", response_model=MessageOut, status_code=201)
def post_message(cid: int, body: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    _require_open(c)
    if body.application_id is not None and body.application_id not in {a.id for a in c.student.applications}:
        raise HTTPException(422, t("Candidature inconnue", "Unknown application"))
    m = CoachingMessage(coaching_id=c.id, author_id=user.id, author_role=role, content=body.content.strip(),
                        application_id=body.application_id,
                        read_by_student=role == "candidat", read_by_advisor=role != "candidat")
    db.add(m)
    db.flush()
    other = _other_party(c, role)
    if other is not None:
        who = _student_name(c) if role == "candidat" else (c.advisor.display_name if c.advisor and role == "conseiller" else "L'équipe")
        preview = m.content if len(m.content) <= 80 else m.content[:77] + "…"
        svc.notify(db, other, f"acc-msg-{m.id}", f"Message de {who} : « {preview} »")
    db.commit()
    return MessageOut(id=m.id, author_role=m.author_role, author_name=_names(db, {user.id}).get(user.id), content=m.content,
                      application_id=m.application_id, created_at=m.created_at, mine=True)


# ---------- Rendez-vous ----------
@router.post("/{cid}/rendez-vous", response_model=MeetingOut, status_code=201)
def propose_meeting(cid: int, body: MeetingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = _get(cid, user, db)
    if c.status != "en_cours":
        raise HTTPException(409, t("Les rendez-vous se prennent une fois le conseiller attribué", "Meetings can be booked once an adviser is assigned"))
    if body.mode not in svc.MEETING_MODES:
        raise HTTPException(422, t(f"Mode inconnu. Valeurs : {list(svc.MEETING_MODES)}", f"Unknown mode. Values: {list(svc.MEETING_MODES)}"))
    start = body.starts_at if body.starts_at.tzinfo else body.starts_at.replace(tzinfo=timezone.utc)
    if start < datetime.now(timezone.utc):
        raise HTTPException(422, t("Choisissez une date à venir", "Choose a future date"))
    m = CoachingMeeting(coaching_id=c.id, proposed_by="candidat" if role == "candidat" else "conseiller", **body.model_dump())
    db.add(m)
    db.flush()
    other = _other_party(c, role)
    if other is not None:
        svc.notify(db, other, f"acc-rdv-{m.id}-propose", f"Rendez-vous proposé le {start:%d/%m/%Y à %H:%M} (UTC) : à confirmer.")
    db.commit()
    return m


@router.patch("/rendez-vous/{mid}", response_model=MeetingOut)
def update_meeting(mid: int, body: MeetingUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(CoachingMeeting, mid)
    if not m:
        raise HTTPException(404, t("Rendez-vous introuvable", "Meeting not found"))
    c, role = _get(m.coaching_id, user, db)
    me = "candidat" if role == "candidat" else "conseiller"
    data = body.model_dump(exclude_unset=True)
    status = data.pop("status", None)
    if status is not None:
        if status not in svc.MEETING_STATUSES:
            raise HTTPException(422, t(f"Statut inconnu. Valeurs : {list(svc.MEETING_STATUSES)}", f"Unknown status. Values: {list(svc.MEETING_STATUSES)}"))
        if status == "confirme" and m.proposed_by == me and role != "admin":
            raise HTTPException(403, t("C'est à l'autre personne de confirmer ce rendez-vous", "The other person must confirm this meeting"))
        if status == "fait" and me != "conseiller":
            raise HTTPException(403, t("Seul le conseiller marque un rendez-vous comme fait", "Only the adviser can mark a meeting as done"))
        m.status = status
    if "starts_at" in data:  # nouvelle date : l'autre doit reconfirmer
        m.starts_at, m.status, m.proposed_by = data.pop("starts_at"), "propose", me
    if "summary" in data and me != "conseiller":
        raise HTTPException(403, t("Le compte rendu est écrit par le conseiller", "The meeting notes are written by the adviser"))
    for k, v in data.items():
        setattr(m, k, v)
    other = _other_party(c, role)
    if other is not None and status in ("confirme", "annule"):
        word = "confirmé" if status == "confirme" else "annulé"
        svc.notify(db, other, f"acc-rdv-{m.id}-{status}", f"Rendez-vous du {m.starts_at:%d/%m/%Y à %H:%M} (UTC) {word}.")
    db.commit()
    return m


# ---------- Administration ----------
@admin_router.get("/accompagnement", response_model=list[AdminCoachingOut])
def admin_list(status: str | None = None, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    q = select(Coaching).order_by(Coaching.created_at.desc())
    if status:
        q = q.where(Coaching.status == status)
    out = []
    for c in db.scalars(q):
        sugg = [_advisor_out(db, a) for a, _n in svc.suggest_advisors(db, c)] if c.status == "demande" else []
        out.append(_out(c, "admin", AdminCoachingOut, student_email=c.student.email, suggestions=sugg))
    return out


@admin_router.post("/accompagnement/{cid}/attribuer", response_model=CoachingOut)
def admin_assign(cid: int, body: AssignIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    c = db.get(Coaching, cid)
    if not c:
        raise HTTPException(404, t("Accompagnement introuvable", "Coaching not found"))
    _require_open(c)
    a = db.get(Advisor, body.advisor_id)
    if not a or not a.active:
        raise HTTPException(404, t("Conseiller introuvable ou inactif", "Adviser not found or inactive"))
    if a.user_id == c.student_id:
        raise HTTPException(422, t("Un conseiller ne peut pas s'accompagner lui-même", "An adviser cannot coach themselves"))
    svc.assign(db, c, a)
    db.commit()
    return _out(c, "admin")


@admin_router.get("/conseillers", response_model=list[AdvisorAdminOut])
def advisors(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [_advisor_out(db, a) for a in db.scalars(select(Advisor).order_by(Advisor.display_name))]


@admin_router.post("/conseillers", response_model=AdvisorAdminOut, status_code=201)
def add_advisor(body: AdvisorIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Donne le rôle de conseiller à un compte existant (la personne crée d'abord son compte)."""
    u = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not u:
        raise HTTPException(404, t("Aucun compte avec cet e-mail : la personne doit d'abord s'inscrire", "No account with this email: the person must sign up first"))
    if u.advisor is not None:
        raise HTTPException(409, t("Ce compte est déjà conseiller", "This account is already an adviser"))
    data = body.model_dump(exclude={"email"})
    a = Advisor(user_id=u.id, **data)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _advisor_out(db, a)


@admin_router.patch("/conseillers/{aid}", response_model=AdvisorAdminOut)
def update_advisor(aid: int, body: AdvisorUpdate, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    a = db.get(Advisor, aid)
    if not a:
        raise HTTPException(404, t("Conseiller introuvable", "Adviser not found"))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return _advisor_out(db, a)



@admin_router.patch("/accompagnement/{cid}/paiement", response_model=AdminCoachingOut)
def admin_payment(cid: int, body: PaymentIn, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Le paiement (Mobile Money, Wave, Orange Money, virement…) se fait hors plateforme dans le MVP :
    l'administrateur indique ici qu'il est reçu."""
    if body.payment_status not in PAYMENT_STATUSES:
        raise HTTPException(422, t("Statut de paiement inconnu", "Unknown payment status"))
    c = db.get(Coaching, cid)
    if not c:
        raise HTTPException(404, "Accompagnement introuvable")
    request.state.audit_details = {"avant": c.payment_status, "apres": body.payment_status, "prix": c.price,
                                   "candidat": c.student.email}
    c.payment_status = body.payment_status
    db.commit()
    return _out(c, "admin", AdminCoachingOut, student_email=c.student.email)
