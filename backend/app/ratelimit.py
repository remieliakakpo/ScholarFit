"""Limitation des tentatives (connexion, inscription, mot de passe oublié…).

Fenêtre glissante gardée en mémoire : suffisant pour une API lancée en un seul processus. Avec
plusieurs processus ou serveurs, chaque processus compte de son côté (passer alors à Redis).
"""
import ipaddress
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import get_settings
from .i18n import t

_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """Adresse du visiteur. Derrière le site Next.js (relais de confiance), on lit X-Forwarded-For
    en partant de la droite : la dernière adresse ajoutée par un relais de confiance fait foi,
    celles écrites par le visiteur lui-même sont ignorées."""
    peer = request.client.host if request.client else "inconnu"
    trusted = get_settings().trusted_proxy_list
    if not _is_trusted(peer, trusted):
        return peer
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    # « * » veut dire « faire confiance au relais qui nous parle », pas aux adresses écrites dans
    # l'en-tête : sinon une adresse inventée par le visiteur, à gauche, serait retenue.
    relays = [p for p in trusted if p != "*"]
    for addr in reversed(forwarded):
        if not _is_trusted(addr, relays):
            return addr
    return forwarded[0] if forwarded else peer


def _is_trusted(addr: str, trusted: list[str]) -> bool:
    if "*" in trusted:
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return addr in trusted
    for entry in trusted:
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def check(key: str, limit: int, window_seconds: int) -> None:
    """Compte une tentative pour `key` ; 429 si `limit` tentatives ont déjà eu lieu dans la fenêtre."""
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(q[0] + window_seconds - now) + 1
            raise HTTPException(
                429,
                t(f"Trop de tentatives. Réessayez dans {_human(retry)}.", f"Too many attempts. Try again in {_human(retry)}."),
                headers={"Retry-After": str(retry)},
            )
        q.append(now)
        if len(_hits) > 50_000:  # garde-fou mémoire : on oublie les clés inactives
            for k in [k for k, v in _hits.items() if not v or v[-1] <= now - 3600]:
                del _hits[k]


def count(key: str, window_seconds: int) -> int:
    now = time.monotonic()
    with _lock:
        q = _hits.get(key)
        if not q:
            return 0
        while q and q[0] <= now - window_seconds:
            q.popleft()
        return len(q)


def record(key: str) -> None:
    with _lock:
        _hits.setdefault(key, deque()).append(time.monotonic())


def reset(prefix: str = "") -> None:
    with _lock:
        for k in [k for k in _hits if k.startswith(prefix)]:
            del _hits[k]


def _human(seconds: int) -> str:
    if seconds < 90:
        return f"{seconds} s"
    minutes = (seconds + 59) // 60
    return f"{minutes} min"


def limit(bucket: str, max_hits: int, per_seconds: int):
    """Dépendance FastAPI : au-delà de max_hits requêtes en per_seconds secondes par adresse, 429."""

    def dep(request: Request) -> None:
        if get_settings().rate_limit_enabled:
            check(f"{bucket}:{client_ip(request)}", max_hits, per_seconds)

    return dep
