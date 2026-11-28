"""Campus Bourses, l'annuaire des programmes de bourses de Campus France (études en France).

Le site public (https://campusbourses.campusfrance.org) est une application qui lit une API JSON
ouverte : la liste des programmes, puis la fiche de chacun. On lit cette API au lieu de la page,
poliment (même rythme et même User-Agent que le reste de la collecte), et chaque fiche passe par la
même extraction que les annonces des autres sites (IA si elle est branchée, règles sinon).
"""
from __future__ import annotations

import html as htmllib
import json
import logging
import time
from datetime import date, timedelta

import httpx

from sqlalchemy.orm import Session

from ..models import Source
from .base import PoliteFetcher

log = logging.getLogger(__name__)

API = "https://bourses-api.campusfrance.org/"
SITE = "https://campusbourses.campusfrance.org/#/program/"

# Champs de la fiche, dans l'ordre de lecture, avec leur intitulé
SECTIONS = [
    ("synthese", "Résumé"), ("description", "Description"), ("montant", "Montant et avantages"),
    ("duree", "Durée"), ("age", "Âge et conditions"), ("countryNote", "Pays éligibles"),
    ("levelNote", "Niveau d'études"), ("domainNote", "Domaines"), ("maitriseLangue", "Langue"),
    ("conditionsSupplementaires", "Autres conditions"), ("inscription", "Comment postuler"),
    ("pieces", "Pièces à fournir"), ("dates", "Dates et calendrier"), ("selection", "Sélection"),
]


def program_url(bourse_id: int | str) -> str:
    return f"{SITE}{bourse_id}"


def program_html(p: dict) -> str:
    """Fiche de l'API mise en page HTML, pour l'extraction commune (titre, sections, liens officiels)."""
    parts = [f"<html><head><title>{htmllib.escape(p.get('title') or '')}</title></head><body><article>",
             f"<h1>{htmllib.escape(p.get('title') or '')}</h1>",
             "<p>Programme de bourse pour étudier en France, publié dans l'annuaire Campus Bourses de Campus France.</p>"]
    for key, label in SECTIONS:
        value = (p.get(key) or "").strip()
        if value:
            body = value if value.startswith("<") else f"<p>{htmllib.escape(value)}</p>"
            parts.append(f"<h2>{label}</h2>{body}")
    links = [(p.get("inscriptionUrl"), "Postuler sur le site officiel")]
    links += [(p.get(f"url{i}"), f"Site officiel : {p.get(f'web{i}') or ''}") for i in (1, 2, 3)]
    for url, label in links:
        if url and url.startswith("http"):
            parts.append(f'<p><a href="{htmllib.escape(url)}">{htmllib.escape(label)}</a></p>')
    parts.append("</article></body></html>")
    return "".join(parts)


def run(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    from .collector import _crawl_detail_pages

    lang = cfg.get("lang", "fr")
    fetcher = PoliteFetcher()
    try:
        programs = json.loads(fetcher.get(f"{API}sgetgrants/{lang}")).get("programs") or []
        # Programmes annuels : la date de fin est celle de la dernière session. On garde ceux encore
        # ouverts et ceux mis à jour depuis moins de 18 mois (reconduits chaque année), récents d'abord.
        today, fresh = date.today().isoformat(), (date.today() - timedelta(days=548)).isoformat()
        programs = [p for p in programs if (p.get("endAt") or "") >= today or (p.get("updatedAt") or "") >= fresh]
        programs.sort(key=lambda p: p.get("updatedAt") or "", reverse=True)
        ids = {program_url(p["bourseId"]): p["bourseId"] for p in programs if p.get("bourseId")}

        def fetch(url: str) -> str:
            # L'API coupe parfois la connexion sans répondre : deux nouvelles tentatives, espacées
            for attempt in range(3):
                try:
                    data = json.loads(fetcher.get(f"{API}sgetgrant/{ids[url]}/{lang}"))
                    break
                except httpx.TransportError:
                    if attempt == 2:
                        raise
                    time.sleep(5 * (attempt + 1))
            if str(data.get("op")) != "1":
                raise RuntimeError(data.get("errmsg") or "fiche indisponible")
            return program_html(data)

        log.info("Campus Bourses : %d programme(s) publiés", len(ids))
        return _crawl_detail_pages(db, source, list(ids), fetcher, cfg.get("limit", 60), aggregator=True,
                                   kinds=dict.fromkeys(ids, "bourse"), fetch=fetch,
                                   defaults={"study_countries": ["FR"]}, overrides={"recurring": True})
    finally:
        fetcher.close()
