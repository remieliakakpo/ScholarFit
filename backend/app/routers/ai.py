"""CV, lettres de motivation, compatibilité avec une bourse, dossiers et exports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import credits, export
from ..ai.cv import build_cv, cv_plain_text, diagnose
from ..ai.fit import fit_check
from ..ai.formats import document_language, letter_style
from ..ai.letter import QUESTIONS, generate_letter, question_label, letter_plain_text, letter_word_count, readiness
from ..db import get_db
from ..i18n import t
from ..models import Application, CreditOrder, Document, Scholarship, User
from ..quota import can_use_ai
from ..routers.profile import get_profile
from ..security import admin_user, current_user

router = APIRouter(prefix="/api", tags=["CV, lettres et dossiers"])


# ------------------------------------------------------------------ schémas
class CVReviewIn(BaseModel):
    text: str | None = None  # vide = CV importé dans le profil
    scholarship_id: int | None = None


class CVAdaptIn(BaseModel):
    scholarship_id: int | None = None
    text: str | None = None


class LetterIn(BaseModel):
    scholarship_id: int
    target_program: str = ""
    why_country: str = ""
    why_program: str = ""
    study_plan: str = ""
    project_after: str = ""
    proud_of: str = ""
    extra: str = ""
    recipient_address: str = ""
    language: str = Field(default="", pattern="^(|fr|en)$")
    max_words: int = Field(default=450, ge=200, le=1000)
    tone: str = "sobre"  # sobre | chaleureux | dynamique


class DocUpdate(BaseModel):
    data: dict


class OrderIn(BaseModel):
    method: str
    reference: str = ""
    payer_phone: str = ""


class OrderStatus(BaseModel):
    status: str


ANSWER_KEYS = [k for k, _ in QUESTIONS] + ["recipient_address"]


# ------------------------------------------------------------------ outils
def _scholarship(sid: int | None, db: Session) -> Scholarship | None:
    if sid is None:
        return None
    s = db.get(Scholarship, sid)
    if not s:
        raise HTTPException(404, t("Bourse introuvable", "Scholarship not found"))
    return s


def _latest_doc(user: User, kind: str, sid: int | None, db: Session) -> Document | None:
    stmt = select(Document).where(Document.user_id == user.id, Document.kind == kind)
    stmt = stmt.where(Document.scholarship_id.is_(None)) if sid is None else stmt.where(Document.scholarship_id == sid)
    return db.scalars(stmt.order_by(Document.id.desc())).first()


def _doc_out(d: Document | None) -> dict | None:
    if d is None:
        return None
    return {"id": d.id, "kind": d.kind, "title": d.title, "data": d.data, "scholarship_id": d.scholarship_id,
            "updated_at": (d.updated_at or d.created_at).isoformat() if (d.updated_at or d.created_at) else None}


def _application(user: User, s: Scholarship, db: Session, create: bool = False) -> Application | None:
    app = db.scalars(select(Application).where(Application.user_id == user.id, Application.scholarship_id == s.id)).first()
    if app is None and create:
        app = Application(user_id=user.id, scholarship_id=s.id, checklist={r: False for r in (s.requirements or ["cv", "lettre"])})
        db.add(app)
    return app


# ------------------------------------------------------------------ CV
@router.post("/cv/review")
def cv_review(body: CVReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Diagnostic du CV : neuf critères, recommandations et réécritures. Gratuit et illimité."""
    p = get_profile(user, db)
    text = (body.text or p.cv_text or "").strip()
    if len(text) < 30:
        raise HTTPException(422, t("Importez votre CV ou collez son contenu pour lancer le diagnostic.", "Import your CV or paste its content to run the diagnostic."))
    s = _scholarship(body.scholarship_id, db)
    return diagnose(text, p, s, use_ai=can_use_ai(user, db), email=user.email)


@router.post("/cv/adapt")
def cv_adapt(body: CVAdaptIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Version du CV adaptée à la bourse et au pays. Compte dans le dossier de la bourse."""
    p = get_profile(user, db)
    text = (body.text or p.cv_text or "").strip()
    if len(text) < 30:
        raise HTTPException(422, t("Importez d'abord votre CV : la version adaptée part de votre parcours réel.", "Import your CV first. The tailored version is built from your real background."))
    s = _scholarship(body.scholarship_id, db)
    pack = credits.use_pack(user, s.id if s else None, "cv", db)
    cv = build_cv(text, p, s, user.email, use_ai=can_use_ai(user, db))
    credits.count_run(pack, "cv")
    title = f"CV : {s.title}" if s else "CV international"
    doc = Document(user_id=user.id, kind="cv_adapte", title=title, content=cv_plain_text(cv), scholarship_id=s.id if s else None, data=cv)
    db.add(doc)
    if s:
        app = _application(user, s, db, create=True)
        app.checklist = {**(app.checklist or {}), "cv": True}
    db.commit()
    return {"document": _doc_out(doc), "credits": credits.summary(user, db)}


@router.get("/cv/adapted")
def cv_adapted(scholarship_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"document": _doc_out(_latest_doc(user, "cv_adapte", scholarship_id, db)), "credits": credits.summary(user, db)}


# ------------------------------------------------------------------ lettres
@router.get("/letters/{scholarship_id}/context")
def letter_context(scholarship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Ce qu'il faut pour rédiger : informations manquantes, langue et disposition, dernière version."""
    s = _scholarship(scholarship_id, db)
    p = get_profile(user, db)
    lang = document_language(s, p)
    doc = _latest_doc(user, "lettre", s.id, db)
    return {
        "missing": readiness(p, user.email),
        "language": lang,
        "style": letter_style(s, lang),
        "questions": [{"key": k, "label": question_label(k, label)} for k, label in QUESTIONS],
        "answers": (doc.data or {}).get("answers", {}) if doc else {},
        "document": _doc_out(doc),
        "credits": credits.summary(user, db),
        "header": {"full_name": p.full_name, "phone": p.phone, "city": p.city, "address": p.address,
                   "residence_country": p.residence_country, "gender": p.gender, "email": user.email},
    }


@router.post("/letters")
def letter(body: LetterIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _scholarship(body.scholarship_id, db)
    p = get_profile(user, db)
    missing = [m for m in readiness(p, user.email) if m["field"] != "cv" or not p.experiences]
    if missing:
        raise HTTPException(422, t("Complétez d'abord : ", "Please complete first: ") + ", ".join(m["label"].lower() for m in missing) + ".")
    language = body.language or document_language(s, p)
    answers = {k: getattr(body, k) for k in ANSWER_KEYS}
    pack = credits.use_pack(user, s.id, "lettre", db)
    out = generate_letter(p, s, answers, language, body.max_words, body.tone, use_ai=can_use_ai(user, db), email=user.email)
    credits.count_run(pack, "lettre")
    out["answers"] = answers
    out["max_words"] = body.max_words
    doc = Document(user_id=user.id, kind="lettre", title=f"Lettre : {s.title}", content=letter_plain_text(out), scholarship_id=s.id, data=out)
    db.add(doc)
    app = _application(user, s, db, create=True)
    app.letter = letter_plain_text(out)
    app.checklist = {**(app.checklist or {}), "lettre": True}
    db.commit()
    return {"document": _doc_out(doc), "word_count": letter_word_count(out), "credits": credits.summary(user, db)}


# ------------------------------------------------------------------ documents
@router.put("/documents/{doc_id}")
def update_document(doc_id: int, body: DocUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Enregistre les modifications faites à la main (gratuit, sans limite)."""
    d = db.get(Document, doc_id)
    if not d or d.user_id != user.id:
        raise HTTPException(404, t("Document introuvable", "Document not found"))
    if d.kind not in ("cv_adapte", "lettre"):
        raise HTTPException(422, t("Ce document ne se modifie pas ici", "This document cannot be edited here"))
    data = {**(d.data or {}), **body.data}
    d.data = data
    if d.kind == "lettre":
        d.content = letter_plain_text(data)
        if d.scholarship_id:
            app = db.scalars(select(Application).where(Application.user_id == user.id, Application.scholarship_id == d.scholarship_id)).first()
            if app:
                app.letter = d.content
    else:
        d.content = cv_plain_text(data)
    db.commit()
    return _doc_out(d)


@router.post("/export/{kind}")
def export_file(kind: str, body: DocUpdate, fmt: str = Query("pdf", pattern="^(pdf|docx)$"), user: User = Depends(current_user)):
    """Fichier PDF ou Word du CV (kind=cv) ou de la lettre (kind=lettre), tel qu'affiché à l'écran."""
    data = body.data
    if kind == "cv":
        content = export.cv_pdf(data) if fmt == "pdf" else export.cv_docx(data)
        name = export.safe_filename("CV", data.get("header", {}).get("name", ""))
    elif kind == "lettre":
        content = export.letter_pdf(data) if fmt == "pdf" else export.letter_docx(data)
        name = export.safe_filename("Lettre-de-motivation" if data.get("language") != "en" else "Cover-letter", data.get("signature", ""))
    else:
        raise HTTPException(404, t("Type de document inconnu", "Unknown document type"))
    media = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


# ------------------------------------------------------------------ compatibilité
@router.get("/scholarships/{scholarship_id}/fit")
def fit(scholarship_id: int, ai: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Compatibilité profil + CV avec la bourse, et améliorations à faire avant de postuler."""
    s = _scholarship(scholarship_id, db)
    p = get_profile(user, db)
    app = _application(user, s, db)
    return fit_check(p, s, app, use_ai=ai and can_use_ai(user, db))


# ------------------------------------------------------------------ dossiers et paiements
@router.get("/credits")
def my_credits(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = credits.summary(user, db)
    orders = db.scalars(select(CreditOrder).where(CreditOrder.user_id == user.id).order_by(CreditOrder.id.desc()).limit(10))
    out["orders"] = [_order_out(o) for o in orders]
    return out


@router.post("/credits/orders", status_code=201)
def new_order(body: OrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = credits.create_order(user, body.method, body.reference, body.payer_phone, db)
    return _order_out(o)


def _order_out(o: CreditOrder) -> dict:
    return {"id": o.id, "amount": o.amount, "currency": o.currency, "method": o.method, "reference": o.reference,
            "payer_phone": o.payer_phone, "status": o.status, "status_label": credits.ORDER_STATUSES.get(o.status, o.status),
            "created_at": o.created_at.isoformat() if o.created_at else None, "email": o.user.email if o.user else None}


@router.get("/admin/credit-orders")
def admin_orders(status: str | None = None, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    stmt = select(CreditOrder).order_by(CreditOrder.id.desc()).limit(200)
    if status:
        stmt = stmt.where(CreditOrder.status == status)
    return [_order_out(o) for o in db.scalars(stmt)]


@router.patch("/admin/credit-orders/{order_id}")
def admin_order_status(order_id: int, body: OrderStatus, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    o = db.get(CreditOrder, order_id)
    if not o:
        raise HTTPException(404, t("Commande introuvable", "Order not found"))
    return _order_out(credits.set_order_status(o, body.status, db))
