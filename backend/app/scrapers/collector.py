"""Connecteurs de collecte, dédoublonnage et enregistrement en base.

Connecteurs disponibles :
- ``json``      : export JSON (fichier local ou URL), format de data/scholarships.json ;
- ``rss``       : flux RSS/Atom ; chaque entrée pointe vers une page de bourse ;
- ``page_list`` : une page « liste de bourses » + un sélecteur CSS des liens vers les fiches.

Pour ajouter une source : une ligne dans data/sources.json (voir le README).
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Scholarship, Source
from ..vocab import DOMAINS, KINDS, LEVELS
from .base import PoliteFetcher, RobotsDisallowed
from .extract import extract

log = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FIELDS = [
    "title", "organization", "official_url", "summary", "levels", "study_countries", "eligible_nationalities",
    "excluded_nationalities", "domains", "languages", "amount", "currency", "amount_period", "coverage",
    "full_funding", "deadline", "recurring", "max_age", "min_grade", "requirements", "language_tests",
    "target_groups", "status", "eligibility", "documents_detail", "extra_documents", "apply_via",
    "application_steps", "apply_url", "link_status", "link_final_url", "deadline_estimated", "previous_deadline",
    "kind", "event_start", "event_end", "city", "remote", "duration", "source_page",
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:180]


RECENTLY_CLOSED_DAYS = 120


def next_occurrence(month_day: str, today: date | None = None) -> date:
    """« 03-15 » → prochain 15 mars (pour les bourses annuelles des données d'exemple)."""
    today = today or date.today()
    month, day = map(int, month_day.split("-"))
    d = date(today.year, month, day)
    return d if d >= today else date(today.year + 1, month, day)


def annual_deadline(month_day: str, today: date | None = None) -> tuple[date, date | None]:
    """Date limite habituelle d'une bourse annuelle → (date retenue, session close récemment ou None).

    Si la date de cette année vient de passer (moins de 4 mois), la bourse est présentée comme
    expirée avec la session suivante estimée : l'étudiant est prévenu au lieu de croire qu'elle est ouverte."""
    today = today or date.today()
    month, day = map(int, month_day.split("-"))
    d = date(today.year, month, day)
    if d >= today:
        return d, None
    nxt = date(today.year + 1, month, day)
    return nxt, (d if (today - d).days <= RECENTLY_CLOSED_DAYS else None)


def clean(record: dict) -> dict:
    out = {k: record[k] for k in FIELDS if k in record}
    if "deadline_month_day" in record and not out.get("deadline"):
        out["deadline"], out["previous_deadline"] = annual_deadline(record["deadline_month_day"])
        out["deadline_estimated"] = True
    if "event_month_day" in record and not out.get("event_start"):
        # conférence annuelle : prochaine édition (date indicative)
        out["event_start"] = next_occurrence(record["event_month_day"])
        out["event_end"] = out["event_start"] + timedelta(days=max(0, int(record.get("event_days", 1)) - 1))
    for k in ("deadline", "previous_deadline", "event_start", "event_end"):
        if isinstance(out.get(k), str):
            out[k] = date.fromisoformat(out[k])
    out["levels"] = [l for l in out.get("levels", []) if l in LEVELS]
    out["domains"] = [d for d in out.get("domains", []) if d in DOMAINS] or ["tous"]
    if out.get("kind") not in KINDS:
        out["kind"] = guess_kind(f"{out.get('title', '')} {out.get('summary', '')}")
    return out


def guess_kind(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(stage|stages|internship|internships|traineeship|stagiaire|intern)\b", t):
        return "stage"
    if re.search(r"\b(conférence|conference|colloque|summit|sommet|forum|symposium|congrès|congress|workshop|atelier)\b", t):
        return "conference"
    return "bourse"


def find_duplicate(db: Session, data: dict) -> Scholarship | None:
    """Même lien officiel, même slug, ou titre très proche chez le même organisme."""
    url = data.get("official_url", "").rstrip("/")
    slug = slugify(data["title"])
    existing = db.scalars(select(Scholarship).where(Scholarship.slug == slug)).first()
    if existing:
        return existing
    # Même lien officiel : doublon seulement si les titres se ressemblent (un même portail
    # peut héberger plusieurs bourses différentes). Seuil plus bas quand l'annonce vient d'un
    # agrégateur, dont les titres sont réécrits (« Bourses Chevening 2027 entièrement financées »).
    threshold = 0.45 if data.get("source_page") else 0.6
    for s in db.scalars(select(Scholarship).where(Scholarship.official_url == url)):
        if SequenceMatcher(None, s.title.lower(), data["title"].lower()).ratio() > threshold:
            return s
    org = (data.get("organization") or "").lower()
    for s in db.scalars(select(Scholarship)):
        same_org = not org or org in s.organization.lower() or s.organization.lower() in org
        if same_org and SequenceMatcher(None, s.title.lower(), data["title"].lower()).ratio() > 0.88:
            return s
    return None


def upsert(db: Session, record: dict, source: Source | None, verified: bool = False) -> tuple[Scholarship, bool]:
    data = clean(record)
    data["official_url"] = data["official_url"].rstrip("/")
    now = datetime.now(timezone.utc)
    existing = find_duplicate(db, data)
    if existing:
        for k, v in data.items():
            if v not in (None, "", [], {}) or k in ("full_funding", "deadline_estimated", "previous_deadline"):
                setattr(existing, k, v)
        existing.collected_at = now
        if verified:
            existing.verified_at = now
        return existing, False
    if not verified:
        data.setdefault("status", "a_verifier")
    slug = slugify(data["title"])
    if db.scalars(select(Scholarship).where(Scholarship.slug == slug)).first():
        slug = f"{slug[:170]}-{slugify(data.get('organization') or 'x')[:8]}"
    s = Scholarship(slug=slug, source=source, collected_at=now, verified_at=now if verified else None, **data)
    if s.deadline and s.deadline < date.today() and not s.recurring:
        s.status = "expiree"
    db.add(s)
    db.flush()
    return s, True


# ------------------------------------------------------------------ connecteurs
def run_json(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    location = cfg.get("path") or source.url
    if location.startswith("http"):
        fetcher = PoliteFetcher()
        try:
            records = json.loads(fetcher.get(location))
        finally:
            fetcher.close()
    else:
        records = json.loads((DATA_DIR / location).read_text(encoding="utf-8"))
    created = updated = 0
    for r in records:
        _, is_new = upsert(db, r, source, verified=cfg.get("trusted", False))
        created += is_new
        updated += not is_new
    return created, updated


def org_from_url(url: str) -> str:
    """Nom lisible de l'organisme d'après le site officiel : « chevening.org » donne « Chevening »."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().split(":")[0]
    parts = [p for p in host.split(".") if p not in ("www", "en", "fr", "apply", "portal")]
    if len(parts) < 2:
        return ""
    name = parts[-3] if len(parts) >= 3 and parts[-2] in ("ac", "co", "gov", "edu", "org", "gouv") else parts[-2]
    return name.upper() if len(name) <= 5 else name.replace("-", " ").title()


def _crawl_detail_pages(db: Session, source: Source, urls: list[str], fetcher: PoliteFetcher, limit: int,
                        aggregator: bool = False, kind: str | None = None) -> tuple[int, int]:
    """``aggregator`` : site qui relaie des offres (Afri-Carrières, Opportunity Desk…). On garde la page vue
    dans ``source_page`` et on remplace le lien par celui du site officiel de l'organisme quand on le trouve."""
    from .extract import official_link

    use_ai = get_settings().ai_enabled
    created = updated = 0
    if aggregator:  # annonces déjà lues : inutile de les relire (et de repayer l'extraction)
        known = set(db.scalars(select(Scholarship.source_page).where(Scholarship.source_page.in_(urls))))
        urls = [u for u in urls if u not in known]
    for url in urls[:limit]:
        try:
            html = fetcher.get(url)
        except RobotsDisallowed:
            log.info("robots.txt interdit %s : ignoré", url)
            continue
        except Exception as e:  # noqa: BLE001 - une page en erreur ne doit pas arrêter la collecte
            log.warning("Échec %s : %s", url, e)
            continue
        record = extract(html, url, use_ai=use_ai)
        if not record or not record.get("title"):
            continue
        record.setdefault("organization", source.name)
        if not record.get("organization"):
            record["organization"] = source.name
        record["source_text"] = None  # on ne stocke pas le texte entier (droit d'auteur)
        if aggregator:
            record["source_page"] = url
            record["recurring"] = False  # une annonce relayée vaut pour une session
            if record.get("official_url", url) == url:
                record["official_url"] = official_link(html, url) or url
            if record.get("organization") == source.name:
                record["organization"] = org_from_url(record["official_url"]) or source.name
        if kind and not record.get("kind"):
            record["kind"] = kind
        _, is_new = upsert(db, record, source)
        created += is_new
        updated += not is_new
    return created, updated


def run_rss(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    fetcher = PoliteFetcher()
    try:
        root = ET.fromstring(fetcher.get(source.url))
        links = [el.text.strip() for el in root.iter() if el.tag.endswith("link") and el.text and el.text.strip().startswith("http")]
        links += [el.attrib["href"] for el in root.iter() if el.tag.endswith("link") and "href" in el.attrib]
        links = [l for l in dict.fromkeys(links) if l.rstrip("/") != source.url.rstrip("/")]
        return _crawl_detail_pages(db, source, links, fetcher, cfg.get("limit", 30))
    finally:
        fetcher.close()


def run_page_list(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    fetcher = PoliteFetcher()
    try:
        soup = BeautifulSoup(fetcher.get(source.url), "html.parser")
        links = [urljoin(source.url, a["href"]) for a in soup.select(cfg.get("link_selector", "a")) if a.get("href")]
        pattern = cfg.get("link_pattern")
        if pattern:
            links = [l for l in links if re.search(pattern, l)]
        links = list(dict.fromkeys(links))
        return _crawl_detail_pages(db, source, links, fetcher, cfg.get("limit", 30))
    finally:
        fetcher.close()


def run_ai_discovery(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    from .discovery import run_ai_discovery as _run

    return _run(db, source, cfg)


ARTICLE_HINT = re.compile(r"(bourse|scholarship|fellowship|stage|internship|traineeship|conference|conférence|summit|sommet|forum|colloque|programme|program|award|grant|prix)", re.I)


JOB_HINT = re.compile(r"(recrute|recrutement|emploi|job|jobs|cdi|cdd|vacancy|hiring|offre-d-emploi)", re.I)


def run_site(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    """Site d'annonces dont on ne connaît pas la structure : on essaie son flux RSS (WordPress : /feed/),
    sinon on lit la page d'accueil et les pages ``paths`` et on garde les liens internes qui ressemblent
    à des annonces d'opportunités."""
    from urllib.parse import urlparse

    fetcher = PoliteFetcher()
    limit = cfg.get("limit", 30)
    base = source.url.rstrip("/")
    host = urlparse(base).netloc
    links: list[str] = []
    try:
        feeds = cfg.get("feeds", [base + "/feed/"])
        pages = int(cfg.get("feed_pages", 1))
        feeds = [f if n == 1 else f"{f}{'&' if '?' in f else '?'}paged={n}" for f in feeds for n in range(1, pages + 1)]
        for feed in feeds:
            try:
                root = ET.fromstring(fetcher.get(feed))
                links += [el.text.strip() for el in root.iter() if el.tag.endswith("link") and el.text and el.text.strip().startswith("http")]
            except Exception as e:  # noqa: BLE001 - pas de flux : on passe aux pages
                log.info("Pas de flux %s (%s)", feed, e)
        if len(links) < 5:
            for path in cfg.get("paths", ["/"]):
                page = urljoin(base + "/", path.lstrip("/"))
                try:
                    soup = BeautifulSoup(fetcher.get(page), "html.parser")
                except Exception as e:  # noqa: BLE001
                    log.info("Page %s ignorée (%s)", page, e)
                    continue
                for a in soup.find_all("a", href=True):
                    href = urljoin(page, a["href"]).split("#")[0]
                    p = urlparse(href)
                    if p.netloc != host or p.path.count("-") < 2:
                        continue
                    text = p.path + " " + a.get_text(" ", strip=True)
                    if JOB_HINT.search(text) and not re.search(r"(stage|intern|trainee)", text, re.I):
                        continue  # offres d'emploi : hors sujet
                    if ARTICLE_HINT.search(text):
                        links.append(href)
        pattern = cfg.get("link_pattern")
        if pattern:
            links = [l for l in links if re.search(pattern, l)]
        links = [l for l in dict.fromkeys(links) if l.rstrip("/") != base]
        return _crawl_detail_pages(db, source, links, fetcher, limit, aggregator=True, kind=cfg.get("kind"))
    finally:
        fetcher.close()


def run_reliefweb(db: Session, source: Source, cfg: dict) -> tuple[int, int]:
    from .reliefweb import run

    return run(db, source, cfg)


CONNECTORS = {"json": run_json, "rss": run_rss, "page_list": run_page_list, "ai_discovery": run_ai_discovery, "site": run_site,
              "reliefweb": run_reliefweb}


def load_source_configs() -> list[dict]:
    return json.loads((DATA_DIR / "sources.json").read_text(encoding="utf-8"))


def sync_sources(db: Session) -> list[Source]:
    out = []
    for cfg in load_source_configs():
        src = db.scalars(select(Source).where(Source.name == cfg["name"])).first()
        if not src:
            src = Source(name=cfg["name"])
            db.add(src)
        src.url = cfg["url"]
        src.method = cfg.get("method", "page")
        src.connector = cfg["connector"]
        src.frequency_hours = cfg.get("frequency_hours", 168)
        if src.enabled is None:
            src.enabled = cfg.get("enabled", True)
        out.append(src)
    db.flush()
    return out


def run_source(db: Session, name: str) -> str:
    cfg = next((c for c in load_source_configs() if c["name"] == name), None)
    if cfg is None:
        raise ValueError(f"Source inconnue : {name}")
    sync_sources(db)
    src = db.scalars(select(Source).where(Source.name == name)).one()
    if src.method not in ("manual", "ai", "api") and not cfg.get("path"):
        fetcher = PoliteFetcher()
        try:
            src.robots_allowed = fetcher.allowed(src.url)
        except Exception:  # noqa: BLE001
            src.robots_allowed = None
        finally:
            fetcher.close()
        src.robots_checked_at = datetime.now(timezone.utc)
        if src.robots_allowed is False:
            src.last_status = "robots.txt interdit la collecte : traiter par lien simple ou partenariat"
            src.last_run_at = datetime.now(timezone.utc)
            db.commit()
            return src.last_status
    try:
        created, updated = CONNECTORS[cfg["connector"]](db, src, cfg)
        src.last_status = f"ok : {created} nouvelle(s), {updated} mise(s) à jour"
    except Exception as e:  # noqa: BLE001
        db.rollback()
        src = db.scalars(select(Source).where(Source.name == name)).one()
        src.last_status = f"erreur : {e}"[:500]
        created = 0
    src.last_run_at = datetime.now(timezone.utc)
    db.commit()
    return src.last_status


def run_all(db: Session, only_enabled: bool = True, only_due: bool = False) -> dict[str, str]:
    """Lance les sources. ``only_due`` : seulement celles dont la fréquence est écoulée (collecte automatique)."""
    results = {}
    now = datetime.now(timezone.utc)
    sync_sources(db)
    for cfg in load_source_configs():
        if only_enabled and not cfg.get("enabled", True):
            continue
        if only_due:
            src = db.scalars(select(Source).where(Source.name == cfg["name"])).first()
            last = src.last_run_at if src else None
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last and (now - last).total_seconds() < cfg.get("frequency_hours", 168) * 3600:
                continue
        results[cfg["name"]] = run_source(db, cfg["name"])
    return results


def expire_old(db: Session) -> int:
    """Passe en « expirée » les bourses dont la date est dépassée ; les bourses annuelles
    sont décalées à l'année suivante et marquées « à vérifier »."""
    from ..deadlines import add_year

    today = date.today()
    n = 0
    for s in db.scalars(select(Scholarship).where(Scholarship.deadline < today, Scholarship.status != "expiree")):
        if s.recurring:
            # La session est close : on garde sa date pour prévenir l'étudiant, et on estime la suivante.
            s.previous_deadline = s.deadline
            s.deadline = add_year(s.deadline)
            s.deadline_estimated = True
            s.status = "a_verifier"
        else:
            s.status = "expiree"
        n += 1
    db.commit()
    return n
