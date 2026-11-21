from datetime import date, datetime, timezone
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.chat import parse_rules
from ..ai.documents import extract_text, split_sections
from ..db import get_db
from ..matching import Criteria, missing_minimum, profile_completeness, rank
from ..models import AIUsage, Document, Profile, Scholarship, ScholarshipReport, User
from ..schemas import MatchesOut, ProfileIn, ProfileOut
from ..security import current_user
from ..serializers import match_out
from ..geo import REGIONS
from ..offers import HELP_PREFERENCES
from ..vocab import COUNTRIES, DOMAINS, LEVELS

router = APIRouter(prefix="/api", tags=["profil et matching"])
MAX_UPLOAD = 5 * 1024 * 1024


def get_profile(user: User, db: Session) -> Profile:
    if user.profile is None:
        user.profile = Profile()
        db.commit()
    return user.profile


def profile_out(p: Profile) -> ProfileOut:
    out = ProfileOut.model_validate(p)
    out.has_cv = bool(p.cv_text)
    out.completeness, out.completeness_tip = profile_completeness(p)
    out.missing_minimum = missing_minimum(Criteria.from_profile(p))
    out.minimum_ok = not out.missing_minimum
    return out


@router.get("/profile", response_model=ProfileOut)
def read_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile_out(get_profile(user, db))


def _row(obj, skip: tuple[str, ...] = ()) -> dict:
    """Toutes les colonnes d'une ligne, en valeurs JSON."""
    out = {}
    for col in sa_inspect(obj).mapper.column_attrs:
        if col.key in skip:
            continue
        v = getattr(obj, col.key)
        out[col.key] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


@router.get("/profile/export")
def export_my_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Droit d'accès et de portabilité : toutes les données liées au compte, dans un fichier JSON."""
    coachings = []
    for c in user.coachings:
        coachings.append({
            **_row(c),
            "steps": [_row(x) for x in c.steps],
            "messages": [_row(x) for x in c.messages],
            "meetings": [_row(x) for x in c.meetings],
        })
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": _row(user, skip=("password_hash", "token_version")),
        "profile": _row(user.profile) if user.profile else None,
        "applications": [{**_row(a), "scholarship_title": a.scholarship.title if a.scholarship else None} for a in user.applications],
        "documents": [_row(d) for d in user.documents],
        "doc_packs": [_row(d) for d in user.doc_packs],
        "payment_declarations": [_row(o) for o in user.credit_orders],
        "coachings": coachings,
        "alerts": [_row(a) for a in user.alerts],
        "ai_usage": [_row(u) for u in db.scalars(select(AIUsage).where(AIUsage.user_id == user.id))],
        "advisor": _row(user.advisor) if user.advisor else None,
        "saved_searches": [_row(x) for x in user.saved_searches],
        "reports": [_row(x) for x in db.scalars(select(ScholarshipReport).where(ScholarshipReport.user_id == user.id))],
    }
    body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return Response(body, media_type="application/json", headers={
        "Content-Disposition": 'attachment; filename="scholarfit-mes-donnees.json"',
        "Cache-Control": "private, no-store",
    })


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_profile(user, db)
    data = body.model_dump(exclude_unset=True)
    for code_field, allowed in (("current_level", LEVELS), ("target_level", LEVELS), ("domain", DOMAINS)):
        if data.get(code_field) and data[code_field] not in allowed:
            raise HTTPException(422, f"Valeur inconnue pour {code_field}")
    for list_field in ("nationalities", "wished_countries"):
        if data.get(list_field):
            bad = [c for c in data[list_field] if c not in COUNTRIES]
            if bad:
                raise HTTPException(422, f"Pays inconnus : {bad}")
    if data.get("wished_regions"):
        bad = [r for r in data["wished_regions"] if r not in REGIONS]
        if bad:
            raise HTTPException(422, f"Régions inconnues : {bad}")
    if data.get("help_preference") and data["help_preference"] not in HELP_PREFERENCES:
        raise HTTPException(422, "Valeur inconnue pour help_preference")
    if data.get("birth_date") and data["birth_date"] > date.today():
        raise HTTPException(422, "Date de naissance dans le futur")
    for k, v in data.items():
        setattr(p, k, v)
    p.sync_sensitive_consent()
    db.commit()
    return profile_out(p)


@router.post("/profile/cv", response_model=ProfileOut)
async def upload_cv(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Import du CV (PDF, Word .docx ou texte). Préremplit le profil quand c'est possible."""
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Fichier trop lourd (5 Mo maximum)")
    try:
        text = extract_text(file.filename or "cv.txt", data)
    except Exception as e:  # noqa: BLE001 - détail technique au journal, pas à l'utilisateur
        import logging

        logging.getLogger(__name__).info("CV illisible (utilisateur %s) : %s", user.id, e)
        raise HTTPException(422, "Impossible de lire ce fichier. Essayez un PDF texte, un .docx ou un .txt.") from e
    if len(text) < 30:
        raise HTTPException(422, "Le fichier ne contient pas de texte lisible (CV scanné ?). Essaie un PDF texte ou un .docx.")
    p = get_profile(user, db)
    p.cv_text = text[:30000]
    db.add(Document(user_id=user.id, kind="cv_original", title=file.filename or "CV", content=p.cv_text))

    # Préremplissage prudent : seulement les champs vides, l'étudiant vérifie ensuite.
    sections = split_sections(text)
    guessed = parse_rules(text)
    if not p.domain and guessed.get("domain"):
        p.domain = guessed["domain"]
    if not p.experiences and sections.get("experiences"):
        p.experiences = sections["experiences"][:2000]
    if not p.engagement and sections.get("engagement"):
        p.engagement = sections["engagement"][:1500]
    if not p.language_scores and guessed.get("language_scores"):
        p.language_scores = guessed["language_scores"]
    db.commit()
    return profile_out(p)


@router.get("/matches", response_model=MatchesOut)
def matches(limit: int = 30, kind: str = Query("bourse", pattern="^(bourse|stage|conference|tout)$"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_profile(user, db)
    c = Criteria.from_profile(p)
    missing = missing_minimum(c)
    if missing:
        return MatchesOut(minimum_ok=False, missing_minimum=missing, excluded_count=0, items=[])
    stmt = select(Scholarship).where(Scholarship.status != "expiree")
    if kind != "tout":
        stmt = stmt.where(Scholarship.kind == kind)
    scholarships = list(db.scalars(stmt))
    results, excluded = rank(scholarships, c, limit=limit)
    return MatchesOut(minimum_ok=True, missing_minimum=[], excluded_count=excluded, items=[match_out(m) for m in results])
