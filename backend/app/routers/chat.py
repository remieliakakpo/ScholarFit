from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.chat import extract_criteria, next_question, summarize_understanding
from ..db import get_db
from ..i18n import t
from ..matching import Criteria, rank
from ..models import Scholarship, User
from ..quota import can_use_ai
from ..schemas import ChatIn, ChatOut, QuickReply
from ..security import optional_user
from ..serializers import match_out
from ..visibility import public_filter

router = APIRouter(prefix="/api", tags=["assistant"])
ANONYMOUS_LIMIT = 3


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    last = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
    previous = dict(body.criteria or {})

    # Si l'étudiant est connecté, on part de son profil.
    if user and user.profile and not previous:
        p = user.profile
        pc = Criteria.from_profile(p)
        previous = {k: v for k, v in {
            "target_level": pc.target_level, "nationalities": pc.nationalities, "age": pc.age,
            "domain": pc.domain, "wished_countries": pc.wished_countries,
            "full_funding_only": pc.full_funding_only or None, "grade_average": pc.grade_average,
            "language_scores": pc.language_scores or None, "situations": pc.situations or None,
        }.items() if v not in (None, [], {})}

    criteria, ai_used = extract_criteria(last, previous, use_ai=can_use_ai(user, db))
    question, replies, missing = next_question(criteria)
    understood = summarize_understanding(criteria)

    if question:
        reply = (t(f"J'ai compris : {understood}. ", f"Here is what I understood: {understood}. ") if understood else "") + question
        return ChatOut(reply=reply, criteria=criteria, missing=missing,
                       quick_replies=[QuickReply(**r) for r in replies], ai_used=ai_used)

    # Profil minimum connu : recherche dans NOTRE base (jamais de réponse de mémoire).
    scholarships = list(db.scalars(select(Scholarship).where(public_filter(), Scholarship.status != "expiree", Scholarship.kind == "bourse")))
    results, excluded = rank(scholarships, Criteria.from_dict(criteria), limit=20)

    # Les critères donnés dans le chat remplissent le profil s'il est vide.
    if user and user.profile:
        p = user.profile
        p.target_level = p.target_level or criteria.get("target_level")
        p.domain = p.domain or criteria.get("domain")
        p.nationalities = p.nationalities or criteria.get("nationalities", [])
        p.wished_countries = p.wished_countries or criteria.get("wished_countries", [])
        db.commit()

    shown = results if user else results[:ANONYMOUS_LIMIT]
    if not results:
        reply = t(f"J'ai compris : {understood}. Aucune bourse ouverte ne correspond à ces critères "
                  f"({excluded} exclues). Élargissez les pays ou acceptez un financement partiel.",
                  f"Here is what I understood: {understood}. No open scholarship matches these criteria "
                  f"({excluded} excluded). Try more countries or accept partial funding.")
        quick = [QuickReply(label=t("N'importe quel pays", "Any country"), value=t("peu importe le pays", "any country")),
                 QuickReply(label=t("Financement partiel accepté", "Partial funding is fine"),
                            value=t("financement partiel accepté", "partial funding is fine"))]
    else:
        reply = t(f"J'ai compris : {understood}. Voici {len(results)} bourse(s) qui vous correspondent, triées par pertinence et date limite.",
                  f"Here is what I understood: {understood}. Here are {len(results)} scholarship(s) that match your profile, "
                  "sorted by relevance and deadline.")
        if not user and len(results) > ANONYMOUS_LIMIT:
            more = len(results) - ANONYMOUS_LIMIT
            reply += t(f" Créez un compte gratuit pour voir les {more} autres et préparer votre dossier.",
                       f" Create a free account to see the other {more} and prepare your application.")
        reply += t(" Vous pouvez affiner : « seulement les bourses complètes », « date limite après mars »…",
                   " You can refine: \"fully funded only\", \"deadline after March\"…")
        quick = [QuickReply(label=t("Seulement financement complet", "Fully funded only"),
                            value=t("seulement les bourses complètes", "fully funded only")),
                 QuickReply(label=t("Date limite après mars", "Deadline after March"),
                            value=t("date limite après mars", "deadline after March"))]
    return ChatOut(reply=reply, criteria=criteria, missing=[], quick_replies=quick,
                   results=[match_out(m) for m in shown], ai_used=ai_used)
