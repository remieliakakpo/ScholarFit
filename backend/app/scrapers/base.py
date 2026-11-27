"""Collecte polie : robots.txt respecté, rythme limité par domaine, User-Agent clair, cache.

Règles (voir le document de conception) :
1. lire robots.txt et ne pas collecter là où c'est interdit ;
2. préférer une API, un flux RSS ou un export officiel ;
3. une requête toutes les quelques secondes par domaine, User-Agent identifiable, cache ;
4. ne stocker que les faits et toujours renvoyer vers la page d'origine ;
5. aucune donnée personnelle collectée ;
6. date de collecte et de vérification gardées pour chaque bourse.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "pages"


class RobotsDisallowed(Exception):
    pass


class PoliteFetcher:
    def __init__(self, min_delay: float | None = None, user_agent: str | None = None, cache_hours: float = 24):
        s = get_settings()
        self.min_delay = s.scraper_min_delay_seconds if min_delay is None else min_delay
        self.user_agent = user_agent or s.scraper_user_agent
        self.cache_seconds = cache_hours * 3600
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self.client = httpx.Client(headers={"User-Agent": self.user_agent}, timeout=20, follow_redirects=True)

    # -- robots.txt
    def robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                if r.status_code >= 400:
                    rp = None  # pas de robots.txt : collecte autorisée
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                log.warning("robots.txt injoignable pour %s : on s'abstient", base)
                rp = RobotFileParser()
                rp.parse(["User-agent: *", "Disallow: /"])
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        rp = self.robots_for(url)
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    # -- rythme
    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last.get(host, 0)
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last[host] = time.monotonic()

    # -- cache disque
    def _cache_path(self, url: str) -> Path:
        return CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest() + ".html")

    def get(self, url: str, use_cache: bool = True) -> str:
        path = self._cache_path(url)
        if use_cache and path.exists() and time.time() - path.stat().st_mtime < self.cache_seconds:
            return path.read_text(encoding="utf-8", errors="ignore")
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        self._wait(url)
        r = self.client.get(url)
        r.raise_for_status()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text, encoding="utf-8")
        return r.text

    def close(self) -> None:
        self.client.close()
