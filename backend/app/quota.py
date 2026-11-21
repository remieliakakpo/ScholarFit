from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AIUsage, User


def can_use_ai(user: User | None, db: Session, consume: bool = True) -> bool:
    """IA réservée aux comptes connectés à l'adresse confirmée, avec un plafond de générations par jour.
    Sans IA, les mêmes fonctions marchent avec les règles hors-ligne."""
    s = get_settings()
    if not s.ai_enabled or user is None or not user.email_verified:
        return False
    today = date.today()
    usage = db.scalars(select(AIUsage).where(AIUsage.user_id == user.id, AIUsage.day == today)).first()
    if usage is None:
        usage = AIUsage(user_id=user.id, day=today, count=0)
        db.add(usage)
    if usage.count >= s.ai_free_generations_per_day:
        return False
    if consume:
        usage.count += 1
        db.commit()
    return True
