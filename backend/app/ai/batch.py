"""Travaux d'IA par lots (Message Batches API : moitié prix sur tous les jetons).

Pour ce qui n'a personne qui attend la réponse : extraction des annonces collectées, mise en forme
des notes de la découverte, traduction des fiches. Le passage de collecte met les travaux en file
(`enqueue`), les envoie en un lot à la fin (`submit_pending`), et au passage suivant récupère les
réponses (`collect_results`) et les applique comme le ferait l'appel immédiat. La plupart des lots
finissent en moins d'une heure (24 h au plus).

En cas d'échec d'un travail (refus, erreur, lot expiré), l'extraction retombe sur les règles
hors-ligne ; une traduction ou une mise en forme ratée est simplement refaite plus tard.
Un lot n'accepte pas le paramètre ``fallbacks`` (relance automatique sur un autre modèle) : un
refus compte donc comme un échec.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AIJob, Scholarship, SeenPage, Source
from . import costs

log = logging.getLogger("lots-ia")
MAX_PER_BATCH = 2000


def _specs() -> dict[str, tuple[str, dict, str, int, str]]:
    """Consignes, schéma JSON, effort, plafond de jetons et modèle de chaque type de travail
    (mêmes réglages que l'appel immédiat)."""
    from ..scrapers.discovery import LIST_SCHEMA, STRUCTURE_SYSTEM
    from ..scrapers.extract import EXTRACT_SCHEMA, EXTRACT_SYSTEM, REVIEW_SCHEMA, REVIEW_SYSTEM
    from ..translate import SCHEMA as TR_SCHEMA
    from ..translate import SYSTEM as TR_SYSTEM

    s = get_settings()
    return {
        # Extraction en deux temps : premier passage économique, relecture ciblée des fiches douteuses
        "extract": (EXTRACT_SYSTEM, EXTRACT_SCHEMA, "low", 8000, s.extract_model),
        "review": (REVIEW_SYSTEM, REVIEW_SCHEMA, "low", 4000, s.review_model_name),
        "structure": (STRUCTURE_SYSTEM, LIST_SCHEMA, "low", 16000, s.claude_model),
        "translate": (TR_SYSTEM, TR_SCHEMA, "low", 4000, s.claude_model),
    }


def enqueue(db: Session, kind: str, user_text: str, context: dict) -> AIJob:
    job = AIJob(kind=kind, user_text=user_text, context=context)
    db.add(job)
    db.flush()
    return job


def pending_targets(db: Session, kind: str, key: str) -> set:
    """Valeurs de context[key] des travaux pas encore terminés (pour ne pas les mettre deux fois en file)."""
    rows = db.scalars(select(AIJob).where(AIJob.kind == kind, AIJob.status.in_(("en_attente", "envoye"))))
    return {(j.context or {}).get(key) for j in rows}


def _client():
    from .client import _get_client

    return _get_client()


def submit_pending(db: Session) -> int:
    """Envoie les travaux en attente en un lot. Renvoie le nombre de travaux envoyés."""
    s = get_settings()
    if not s.ai_enabled or costs.over_budget():
        return 0
    jobs = list(db.scalars(select(AIJob).where(AIJob.status == "en_attente").order_by(AIJob.id).limit(MAX_PER_BATCH)))
    if not jobs:
        return 0
    client = _client()
    if client is None:
        return 0
    specs = _specs()
    requests = []
    for j in jobs:
        system, schema, effort, max_tokens, model = specs[j.kind]
        requests.append({
            "custom_id": f"job-{j.id}",
            "params": {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": j.user_text}],
                "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            },
        })
    try:
        batch = client.messages.batches.create(requests=requests)
    except Exception as e:  # noqa: BLE001 - erreur de l'API : les travaux restent en attente pour le prochain passage
        log.warning("Envoi du lot impossible : %s", e)
        return 0
    now = datetime.now(timezone.utc)
    for j in jobs:
        j.status, j.batch_id, j.updated_at = "envoye", batch.id, now
    db.commit()
    log.info("Lot %s envoyé : %d travaux", batch.id, len(jobs))
    return len(jobs)


def collect_results(db: Session) -> dict[str, int]:
    """Applique les réponses des lots terminés. Renvoie le nombre de travaux faits et échoués."""
    out = {"faits": 0, "echecs": 0}
    batch_ids = sorted({b for b in db.scalars(select(AIJob.batch_id).where(AIJob.status == "envoye")) if b})
    if not batch_ids:
        return out
    client = _client()
    if client is None:
        return out
    for bid in batch_ids:
        try:
            batch = client.messages.batches.retrieve(bid)
        except Exception as e:  # noqa: BLE001
            log.warning("Lot %s illisible : %s", bid, e)
            continue
        if batch.processing_status != "ended":
            continue
        jobs = {j.id: j for j in db.scalars(select(AIJob).where(AIJob.batch_id == bid, AIJob.status == "envoye"))}
        for result in client.messages.batches.results(bid):
            try:
                job = jobs.pop(int(str(result.custom_id).removeprefix("job-")), None)
            except ValueError:
                continue
            if job is None:
                continue
            ok = _apply_result(db, job, result)
            out["faits" if ok else "echecs"] += 1
        for job in jobs.values():  # absents des résultats : on les traite comme échoués
            _fail(db, job, "absent des résultats du lot")
            out["echecs"] += 1
    return out


def _apply_result(db: Session, job: AIJob, result) -> bool:
    r = result.result
    if r.type != "succeeded":
        _fail(db, job, f"lot : {r.type}")
        return False
    msg = r.message
    costs.record(getattr(msg, "usage", None), getattr(msg, "model", None) or get_settings().claude_model,
                 f"lot_{job.kind}", discount=0.5)
    if msg.stop_reason in ("refusal", "max_tokens"):
        _fail(db, job, f"réponse inutilisable ({msg.stop_reason})")
        return False
    text = next((b.text for b in msg.content if b.type == "text"), None)
    try:
        data = json.loads(text or "")
    except ValueError:
        _fail(db, job, "JSON invalide")
        return False
    try:
        HANDLERS[job.kind](db, job, data)
        job.status, job.error = "fait", None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as e:  # noqa: BLE001 - un travail raté ne doit pas bloquer les autres
        db.rollback()
        log.exception("Réponse du travail %s non appliquée", job.id)
        _fail(db, job, f"application : {e}"[:500])
        return False


def _fail(db: Session, job: AIJob, reason: str) -> None:
    try:
        if job.kind == "extract":  # repli : extraction par règles, comme sans IA
            from ..scrapers.extract import extract_rules, split_prompt

            title, text, url = split_prompt(job.user_text)
            _save_extract(db, job, extract_rules(title, text, url))
        elif job.kind == "review":  # relecture ratée : on garde la fiche du premier passage
            from ..scrapers.extract import ai_record

            ctx = job.context or {}
            _save_extract(db, job, ai_record(ctx.get("draft") or {}, ctx["url"]))
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Repli par règles impossible pour le travail %s", job.id)
    job.status, job.error = "echec", reason[:500]
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


# ---------------------------------------------------------------- application des réponses
def _save_extract(db: Session, job: AIJob, record: dict | None) -> None:
    from ..scrapers.collector import finish_record

    ctx = job.context or {}
    source = db.get(Source, ctx["source_id"]) if ctx.get("source_id") else None
    is_new = finish_record(db, source, record, ctx)
    page = db.scalars(select(SeenPage).where(SeenPage.url == ctx.get("url"))).first()
    if page is not None:
        page.outcome = "ecartee" if is_new is None else "fiche"


def _handle_extract(db: Session, job: AIJob, data: dict) -> None:
    """Premier passage reçu : contrôle sans IA ; fiche douteuse → relecture ciblée (lot suivant), sinon enregistrée."""
    from ..scrapers.extract import ai_record, review_reasons, split_prompt

    ctx = job.context or {}
    _title, text, _url = split_prompt(job.user_text)
    reasons = review_reasons(data, text)
    if reasons:
        queue_review(db, job.user_text, data, reasons, ctx)
        return
    _save_extract(db, job, ai_record(data, ctx["url"]))


def queue_review(db: Session, extract_request: str, draft: dict, reasons: list[str], ctx: dict) -> AIJob:
    from ..scrapers.extract import review_prompt

    return enqueue(db, "review", review_prompt(extract_request, draft, reasons), {**ctx, "draft": draft, "reasons": reasons})


def _handle_review(db: Session, job: AIJob, data: dict) -> None:
    from ..scrapers.extract import ai_record, apply_review

    ctx = job.context or {}
    _save_extract(db, job, ai_record(apply_review(ctx.get("draft") or {}, data), ctx["url"]))


def _handle_structure(db: Session, job: AIJob, data: dict) -> None:
    from ..scrapers.discovery import save_found

    ctx = job.context or {}
    source = db.get(Source, ctx["source_id"]) if ctx.get("source_id") else None
    found = data.get("scholarships", [])
    created, updated = save_found(db, source, found, ctx.get("kind") or "bourse")
    log.info("Zone %s : %d proposée(s), %d nouvelle(s), %d mise(s) à jour", ctx.get("zone"), len(found), created, updated)


def _handle_translate(db: Session, job: AIJob, data: dict) -> None:
    from ..translate import apply_translation, fingerprint

    ctx = job.context or {}
    s = db.get(Scholarship, ctx.get("scholarship_id"))
    if s is None or fingerprint(s) != ctx.get("hash"):
        return  # fiche supprimée ou modifiée entre-temps : la prochaine collecte la retraduira
    apply_translation(s, data)


HANDLERS = {"extract": _handle_extract, "review": _handle_review, "structure": _handle_structure, "translate": _handle_translate}
