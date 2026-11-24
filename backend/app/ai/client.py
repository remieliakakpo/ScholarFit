"""Accès à l'API Claude, avec repli hors-ligne.

Si ANTHROPIC_API_KEY n'est pas défini, ou si l'appel échoue, les fonctions renvoient
None et chaque fonctionnalité utilise sa version par règles. La plateforme reste donc
utilisable en local sans clé.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import get_settings
from . import costs

log = logging.getLogger(__name__)

_client = None
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _caller_purpose() -> str:
    """Fonction qui appelle l'IA, d'après le module appelant (app.ai.cv → « cv »), pour le suivi des coûts."""
    import sys

    frame = sys._getframe(1)
    while frame is not None and frame.f_globals.get("__name__") == __name__:
        frame = frame.f_back
    name = frame.f_globals.get("__name__", "autre") if frame is not None else "autre"
    return name.rsplit(".", 1)[-1][:40]


def _get_client():
    global _client
    s = get_settings()
    if not s.ai_enabled:
        return None
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    return _client


def supports_fallbacks(model: str) -> bool:
    """Relance automatique sur un autre modèle en cas de refus : pas proposée pour Claude Haiku 5.5."""
    return not model.startswith("claude-haiku")


def _cache_key(system: str, user: str, effort: str, output_format: dict | None, model: str | None = None) -> str:
    import hashlib

    raw = json.dumps([model or get_settings().claude_model, system, user, effort, output_format], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> str | None:
    from datetime import datetime, timedelta, timezone

    from ..db import SessionLocal
    from ..models import AICache

    try:
        db = SessionLocal()
        try:
            row = db.query(AICache).filter_by(key=key).first()
            if row is None:
                return None
            created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
            if created < datetime.now(timezone.utc) - timedelta(days=get_settings().ai_cache_days):
                return None
            return row.value.get("text")
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - sans cache, on appelle simplement l'API
        return None


def _cache_put(key: str, text: str) -> None:
    from datetime import datetime, timezone

    from ..db import SessionLocal
    from ..models import AICache

    try:
        db = SessionLocal()
        try:
            row = db.query(AICache).filter_by(key=key).first()
            if row is None:
                db.add(AICache(key=key, value={"text": text}))
            else:
                row.value, row.created_at = {"text": text}, datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        log.exception("Réponse IA non mise en cache")


def _call(system: str, user: str, *, effort: str, max_tokens: int, output_format: dict | None = None,
          purpose: str | None = None, cache: bool = False, model: str | None = None):
    purpose = purpose or _caller_purpose()
    model = model or get_settings().claude_model
    key = _cache_key(system, user, effort, output_format, model) if cache and get_settings().ai_cache_days > 0 else None
    if key:
        hit = _cache_get(key)
        if hit is not None:  # même demande que récemment : aucune dépense
            return hit
    client = _get_client()
    if client is None or costs.over_budget():
        return None
    import anthropic

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": effort},
    }
    if supports_fallbacks(model):
        # En cas de refus par un filtre de sécurité, l'API relance la requête sur un autre modèle.
        kwargs["betas"] = [FALLBACK_BETA]
        kwargs["fallbacks"] = "default"
    if output_format:
        kwargs["output_config"]["format"] = output_format
    try:
        response = client.beta.messages.create(**kwargs)
    except anthropic.RateLimitError:
        log.warning("Limite de débit Claude atteinte, repli hors-ligne")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Erreur API Claude %s : %s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("Impossible de joindre l'API Claude, repli hors-ligne")
        return None
    costs.record(getattr(response, "usage", None), getattr(response, "model", None) or kwargs["model"], purpose)
    if response.stop_reason in ("refusal", "max_tokens"):
        log.warning("Réponse Claude inutilisable (stop_reason=%s)", response.stop_reason)
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    if key and text:
        _cache_put(key, text)
    return text


def ask_text(system: str, user: str, *, effort: str = "medium", max_tokens: int = 8000, purpose: str | None = None) -> str | None:
    return _call(system, user, effort=effort, max_tokens=max_tokens, purpose=purpose)


def ask_json(system: str, user: str, schema: dict, *, effort: str = "low", max_tokens: int = 8000,
             purpose: str | None = None, cache: bool = False, model: str | None = None) -> dict | None:
    """cache=True : une demande identique faite récemment (AI_CACHE_DAYS) reprend la réponse gardée, sans appel."""
    text = _call(
        system,
        user,
        effort=effort,
        max_tokens=max_tokens,
        output_format={"type": "json_schema", "schema": schema},
        purpose=purpose or _caller_purpose(),
        cache=cache,
        model=model,
    )
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("JSON invalide renvoyé par Claude")
        return None


def ask_web(system: str, user: str, *, max_searches: int = 6, effort: str = "medium", max_tokens: int = 16000) -> str | None:
    """Recherche sur le web (outil serveur de Claude) puis réponse en texte.

    Sert à la découverte de nouvelles bourses. Les résultats sont ensuite structurés par
    ``ask_json`` et chaque lien est vérifié avant d'être affiché.
    """
    client = _get_client()
    if client is None or costs.over_budget():
        return None
    import anthropic

    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches}]
    texts: list[str] = []
    for _ in range(4):  # un tour long peut être mis en pause : on le relance (pause_turn)
        try:
            response = client.beta.messages.create(
                model=get_settings().claude_model, max_tokens=max_tokens, system=system, messages=messages,
                tools=tools, output_config={"effort": effort},
                betas=[FALLBACK_BETA], fallbacks="default",
            )
        except anthropic.RateLimitError:
            log.warning("Limite de débit Claude atteinte pendant la recherche web")
            return None
        except anthropic.APIStatusError as e:
            log.warning("Erreur API Claude %s : %s", e.status_code, e.message)
            return None
        except anthropic.APIConnectionError:
            log.warning("Impossible de joindre l'API Claude")
            return None
        costs.record(getattr(response, "usage", None), getattr(response, "model", None) or get_settings().claude_model, "recherche_web")
        texts += [b.text for b in response.content if b.type == "text"]
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason == "refusal":
            return None
        break
    return "\n".join(texts) or None
