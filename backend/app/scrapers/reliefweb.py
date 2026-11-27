"""Stages des organisations internationales et des ONG, via l'API publique de ReliefWeb (ONU OCHA).

ReliefWeb publie les offres des agences de l'ONU, des ONG et des organisations internationales du
monde entier, avec le pays, l'organisme et la date de clôture. On ne garde que le type « Internship ».
L'API demande un nom d'application approuvé : le demander sur https://apidoc.reliefweb.int puis le
mettre dans .env (RELIEFWEB_APPNAME).
"""
from __future__ import annotations

import logging
import re
from datetime import date

import httpx
import pycountry
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Source

log = logging.getLogger(__name__)

API = "https://api.reliefweb.int/v2/jobs"
CATEGORY_DOMAINS = {
    "information and communications technology": "informatique",
    "health": "medecine",
    "medical": "medecine",
    "agriculture": "agriculture",
    "food security": "agriculture",
    "logistics": "economie",
    "administration": "economie",
    "finance": "economie",
    "human resources": "economie",
    "program/project management": "relations_internationales",
    "monitoring and evaluation": "sciences_sociales",
    "advocacy/communications": "journalisme",
    "legal": "droit",
    "protection": "droit",
    "education": "education",
    "environment": "biologie",
    "water, sanitation and hygiene": "ingenierie",
    "engineering": "ingenierie",
    "energy": "energie",
}
URL = re.compile(r"https?://[^\s)\]>\"']+")


def iso2(iso3: str | None) -> str | None:
    if not iso3:
        return None
    c = pycountry.countries.get(alpha_3=iso3.upper())
    return c.alpha_2 if c else None


def _summary(body: str) -> str:
    text = re.sub(r"[#*_>\[\]]", "", body or "")
    text = re.sub(r"\(https?://[^)]*\)", "", text)
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(sentences[:2])[:600]


def to_record(item: dict, domains: dict) -> dict | None:
    f = item.get("fields") or {}
    title = (f.get("title") or "").strip()
    if not title:
        return None
    page = f.get("url_alias") or f.get("url") or f"https://reliefweb.int/job/{item.get('id')}"
    official = next((u for u in URL.findall(f.get("how_to_apply") or "") if "reliefweb.int" not in u), None)
    countries = [c for c in (iso2(x.get("iso3")) for x in f.get("country") or []) if c]
    org = ", ".join(s.get("name", "") for s in f.get("source") or []).strip(", ")
    closing = (f.get("date") or {}).get("closing")
    deadline = None
    if closing:
        try:
            deadline = date.fromisoformat(closing[:10])
        except ValueError:
            deadline = None
    cats = [c.get("name", "").lower() for c in f.get("career_categories") or []]
    doms = sorted({CATEGORY_DOMAINS[c] for c in cats if CATEGORY_DOMAINS.get(c) in domains}) or ["tous"]
    return {
        "kind": "stage",
        "title": title[:300],
        "organization": org or "Organisation internationale",
        "official_url": (official or page).rstrip(".,;"),
        "source_page": page,
        "summary": _summary(f.get("body") or ""),
        "study_countries": countries,
        "eligible_nationalities": ["ALL"],
        "levels": ["BAC3", "BAC5"],
        "domains": doms,
        "deadline": deadline,
        "recurring": False,
        "requirements": ["cv", "lettre"],
    }


def fetch(appname: str, limit: int, client: httpx.Client) -> list[dict]:
    payload = {
        "filter": {"field": "type.name", "value": "Internship"},
        "fields": {"include": ["title", "url", "url_alias", "body", "how_to_apply", "country.iso3", "source.name",
                               "date.closing", "career_categories.name"]},
        "sort": ["date.created:desc"],
        "limit": min(limit, 1000),
    }
    r = client.post(API, params={"appname": appname}, json=payload)
    r.raise_for_status()
    return r.json().get("data") or []


def run(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    from ..vocab import DOMAINS
    from .collector import upsert

    appname = get_settings().reliefweb_appname
    if not appname:
        raise RuntimeError("ajoutez RELIEFWEB_APPNAME dans backend/.env (nom d'application ReliefWeb)")
    created = updated = 0
    with httpx.Client(timeout=30) as client:
        items = fetch(appname, int(cfg.get("limit", 300)), client)
    for item in items:
        rec = to_record(item, DOMAINS)
        if not rec:
            continue
        if rec["deadline"] and rec["deadline"] < date.today():
            continue
        _, is_new = upsert(db, rec, source)
        created += is_new
        updated += not is_new
    db.commit()
    log.info("ReliefWeb : %d stage(s) reçus", len(items))
    return created, updated
