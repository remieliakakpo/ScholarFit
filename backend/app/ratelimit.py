"""Limite de requêtes par adresse IP, en mémoire (suffisant pour une instance de l'API).

Protège la connexion, l'inscription, le mot de passe oublié et l'assistant contre les robots et les
essais de mots de passe en série. Avec plusieurs instances, passer à Redis (voir DEPLOIEMENT.md).
"""
from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import get_settings
from .i18n import t

_hits: dict[tuple[str, str], deque] = {}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    # Derrière Vercel et Railway, l'adresse réelle est la première de X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def limit(bucket: str, max_hits: int, per_seconds: int):
    """Dépendance FastAPI : au-delà de max_hits requêtes en per_seconds secondes, réponse 429."""

    def dep(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        key = (bucket, client_ip(request))
        now = time.monotonic()
        with _lock:
            q = _hits.setdefault(key, deque())
            while q and now - q[0] > per_seconds:
                q.popleft()
            if len(q) >= max_hits:
                wait = int(per_seconds - (now - q[0])) + 1
                raise HTTPException(429, t(f"Trop de tentatives. Réessayez dans {max(1, wait // 60) if wait >= 60 else wait} "
                                           f"{'minute(s)' if wait >= 60 else 'seconde(s)'}.",
                                           f"Too many attempts. Please try again in {max(1, wait // 60) if wait >= 60 else wait} "
                                           f"{'minute(s)' if wait >= 60 else 'second(s)'}."))
            q.append(now)
            if len(_hits) > 50_000:  # mémoire bornée
                _hits.clear()

    return dep


def reset() -> None:
    with _lock:
        _hits.clear()
