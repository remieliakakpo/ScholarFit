"""Garde-fous réseau pour les adresses venues de l'extérieur (pages collectées, IA, utilisateurs).

1. `http_url` : n'accepte qu'un lien http(s) avec un nom de domaine. Un lien `javascript:` ou
   `data:` enregistré comme « site officiel » s'exécuterait chez chaque visiteur qui clique.
2. `guard_request` : crochet httpx appelé avant chaque requête, redirections comprises. Il refuse
   les adresses internes (localhost, réseau privé, métadonnées du cloud 169.254.169.254…) : sinon
   une page collectée pourrait faire interroger par le serveur des services qui ne sont joignables
   que de l'intérieur (SSRF).
"""
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx


class BlockedAddress(httpx.HTTPError):
    """Adresse interne refusée (sous-classe de HTTPError : traitée comme un lien injoignable)."""

    def __init__(self, message: str, request: httpx.Request | None = None) -> None:
        super().__init__(message)
        if request is not None:
            self.request = request


def http_url(value: str | None) -> str | None:
    """Le lien nettoyé s'il est en http(s) avec un nom de domaine, sinon ValueError."""
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        parts = urlsplit(v)
    except ValueError as e:
        raise ValueError("adresse illisible") from e
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("seuls les liens http:// ou https:// sont acceptés")
    if any(c in v for c in "\r\n\t") or " " in parts.netloc:
        raise ValueError("adresse invalide")
    return v


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def public_host(host: str, port: int | None = None) -> bool:
    """Vrai si toutes les adresses du nom sont publiques."""
    try:
        infos = socket.getaddrinfo(host, port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return True  # nom inconnu : la connexion échouera d'elle-même, rien d'interne n'est atteint
    return all(is_public_ip(info[4][0]) for info in infos)


def guard_request(request: httpx.Request) -> None:
    from .config import get_settings

    if get_settings().fetch_allow_private:
        return
    url = request.url
    if url.scheme not in ("http", "https"):
        raise BlockedAddress(f"protocole refusé : {url.scheme}", request)
    if not public_host(url.host, url.port):
        raise BlockedAddress(f"adresse interne refusée : {url.host}", request)


def safe_client(**kwargs) -> httpx.Client:
    """httpx.Client qui refuse les adresses internes, y compris après une redirection."""
    hooks = kwargs.pop("event_hooks", {}) or {}
    hooks = {**hooks, "request": [guard_request, *hooks.get("request", [])]}
    return httpx.Client(event_hooks=hooks, **kwargs)
