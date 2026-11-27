from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.chat import parse_rules
from ..ai.documents import extract_text, split_sections
from ..db import get_db
from ..matching import Criteria, missing_minimum, profile_completeness, rank
from ..models import Document, Profile, Scholarship, User
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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Impossible de lire ce fichier : {e}") from e
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
