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


def _call(system: str, user: str, *, effort: str, max_tokens: int, output_format: dict | None = None,
          purpose: str | None = None):
    purpose = purpose or _caller_purpose()
    client = _get_client()
    if client is None or costs.over_budget():
        return None
    import anthropic

    kwargs: dict[str, Any] = {
        "model": get_settings().claude_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": effort},
        # En cas de refus par un filtre de sécurité, l'API relance la requête sur un autre modèle.
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }
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
    return next((b.text for b in response.content if b.type == "text"), None)


def ask_text(system: str, user: str, *, effort: str = "medium", max_tokens: int = 8000, purpose: str | None = None) -> str | None:
    return _call(system, user, effort=effort, max_tokens=max_tokens, purpose=purpose)


def ask_json(system: str, user: str, schema: dict, *, effort: str = "low", max_tokens: int = 8000,
             purpose: str | None = None) -> dict | None:
    text = _call(
        system,
        user,
        effort=effort,
        max_tokens=max_tokens,
        output_format={"type": "json_schema", "schema": schema},
        purpose=purpose or _caller_purpose(),
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
