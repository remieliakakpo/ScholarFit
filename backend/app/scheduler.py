"""Collecte automatique pendant que l'API tourne.

Toutes les AUTO_COLLECT_HOURS heures (24 par défaut) : sources dues (dont la découverte par IA),
expirations, vérification des liens, version anglaise des nouvelles fiches, alertes et rappels. Mettre AUTO_COLLECT_HOURS=0 pour
désactiver et planifier plutôt « python -m app.cli nightly » (cron, Planificateur de tâches Windows).
Avec plusieurs instances de l'API, n'activer la collecte que sur une seule.
"""
from __future__ import annotations

import logging
import threading

from .config import get_settings

log = logging.getLogger("collecte-auto")
_stop = threading.Event()
_thread: threading.Thread | None = None


def run_cycle() -> dict:
    """Un passage complet. Utilisé par le planificateur et par « python -m app.cli nightly »."""
    from .alerts import run_alerts
    from .coaching import run_reminders
    from .db import SessionLocal
    from .linkcheck import check_links
    from .scrapers.collector import expire_old, run_all
    from .translate import translate_missing

    db = SessionLocal()
    try:
        report = {"sources": run_all(db, only_due=True)}
        report["expirees"] = expire_old(db)
        report["liens"] = check_links(db)
        report["traductions"] = translate_missing(db, limit=100)
        report["alertes"] = run_alerts(db)
        report["rappels"] = run_reminders(db)
        from .alerts import send_alert_emails

        report["emails"] = send_alert_emails(db)
        return report
    finally:
        db.close()


def _loop(hours: float) -> None:
    _stop.wait(60)  # laisse l'API démarrer
    while not _stop.is_set():
        try:
            log.info("Collecte automatique : %s", run_cycle())
        except Exception:  # noqa: BLE001 - un échec ne doit pas arrêter l'API
            log.exception("Échec de la collecte automatique")
        _stop.wait(hours * 3600)


def start() -> None:
    global _thread
    hours = get_settings().auto_collect_hours
    if hours <= 0 or _thread is not None:
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(hours,), name="collecte-auto", daemon=True)
    _thread.start()
    log.info("Collecte automatique activée : toutes les %s h", hours)


def stop() -> None:
    global _thread
    _stop.set()
    _thread = None
