"""Suivi du coût de l'IA : une ligne par appel (table ai_costs) et plafond de dépense par jour.

Les jetons viennent de `response.usage` (input_tokens, output_tokens, cache_read_input_tokens,
cache_creation_input_tokens, server_tool_use.web_search_requests) ; les prix sont réglables dans
app/config.py (AI_PRICE_*). Un échec d'écriture ne bloque jamais la réponse.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func, select

from ..config import get_settings

log = logging.getLogger(__name__)


def _n(obj, name: str) -> int:
    v = getattr(obj, name, None) if obj is not None else None
    return int(v or 0)


def prices(model: str | None) -> tuple[float, float, float, float]:
    """(entrée, sortie, lecture du cache, écriture du cache) par million de jetons, selon le modèle."""
    s = get_settings()
    if model and "haiku" in model:
        return (s.ai_price_small_input_per_mtok, s.ai_price_small_output_per_mtok,
                s.ai_price_small_cache_read_per_mtok, s.ai_price_small_input_per_mtok * 1.25)
    return (s.ai_price_input_per_mtok, s.ai_price_output_per_mtok, s.ai_price_cache_read_per_mtok, s.ai_price_cache_write_per_mtok)


def estimate(usage, model: str | None = None) -> dict:
    s = get_settings()
    p_in, p_out, p_read, p_write = prices(model)
    tokens = {
        "input_tokens": _n(usage, "input_tokens"),
        "output_tokens": _n(usage, "output_tokens"),
        "cache_read_tokens": _n(usage, "cache_read_input_tokens"),
        "cache_write_tokens": _n(usage, "cache_creation_input_tokens"),
        "web_searches": _n(getattr(usage, "server_tool_use", None), "web_search_requests"),
    }
    cost = (
        tokens["input_tokens"] * p_in
        + tokens["output_tokens"] * p_out
        + tokens["cache_read_tokens"] * p_read
        + tokens["cache_write_tokens"] * p_write
    ) / 1_000_000 + tokens["web_searches"] * s.ai_price_per_web_search
    return {**tokens, "cost_usd": round(cost, 6)}


def record(usage, model: str, purpose: str, discount: float = 1.0) -> None:
    """discount=0.5 pour les lots (Batch API : moitié prix sur tous les jetons)."""
    from ..db import SessionLocal
    from ..models import AICost

    try:
        row = estimate(usage, model)
        row["cost_usd"] = round(row["cost_usd"] * discount, 6)
        db = SessionLocal()
        try:
            db.add(AICost(day=date.today(), model=model[:80], purpose=purpose[:40], **row))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        log.exception("Coût IA non enregistré")


def spent_today() -> float:
    from ..db import SessionLocal
    from ..models import AICost

    db = SessionLocal()
    try:
        return float(db.scalar(select(func.coalesce(func.sum(AICost.cost_usd), 0.0)).where(AICost.day == date.today())) or 0.0)
    finally:
        db.close()


def over_budget() -> bool:
    budget = get_settings().ai_daily_budget_usd
    if budget <= 0:
        return False
    try:
        spent = spent_today()
    except Exception:  # noqa: BLE001 - en cas de doute, on n'empêche pas le service
        return False
    if spent >= budget:
        log.warning("Plafond IA du jour atteint (%.2f $ / %.2f $) : repli hors-ligne", spent, budget)
        return True
    return False
