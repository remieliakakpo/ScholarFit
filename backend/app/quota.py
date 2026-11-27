from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AIUsage, User


def can_use_ai(user: User | None, db: Session, consume: bool = True) -> bool:
    """IA réservée aux comptes connectés, avec un plafond de générations par jour."""
    s = get_settings()
    if not s.ai_enabled or user is None:
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
