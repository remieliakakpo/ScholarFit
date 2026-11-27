"""Commandes d'administration.

    python -m app.cli seed            # crée la base, charge les données d'exemple et deux comptes de démo
    python -m app.cli collect         # lance toutes les sources activées (data/sources.json)
    python -m app.cli collect --source "Données d'exemple"
    python -m app.cli extract URL     # teste l'extraction d'une page (n'enregistre rien)
    python -m app.cli nightly         # sources dues, découverte IA, expirations, liens, alertes (cron / Planificateur Windows)
    python -m app.cli discover        # découverte IA de bourses dans le monde entier (5 zones par passage)
    python -m app.cli check-links     # teste tous les liens officiels et signale les liens morts
"""
import argparse
import json
import logging

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal, init_db
from .models import Source
from .scrapers.base import PoliteFetcher, RobotsDisallowed
from .scrapers.collector import run_all, run_source
from .scrapers.extract import extract

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        print(run_source(db, "Données d'exemple"))
        from .translate import load_seed_translations

        print(f"Version anglaise : {load_seed_translations(db)} fiche(s)")
        from .demo import ensure_demo_accounts

        ensure_demo_accounts(db, verbose=True)
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    c = sub.add_parser("collect")
    c.add_argument("--source")
    e = sub.add_parser("extract")
    e.add_argument("url")
    sub.add_parser("nightly")
    d = sub.add_parser("discover")
    d.add_argument("--zones", type=int, default=5, help="nombre de zones du monde à parcourir (46 au total)")
    tr = sub.add_parser("translate", help="version anglaise des fiches qui n'en ont pas (IA)")
    tr.add_argument("--limit", type=int, default=500)
    sub.add_parser("check-config", help="vérifie les réglages avant la mise en ligne")
    ma = sub.add_parser("make-admin", help="donne les droits d'administrateur à un compte existant (adresse confirmée d'office)")
    ma.add_argument("email")
    te = sub.add_parser("test-email", help="envoie un e-mail d'essai pour vérifier EMAIL_BACKEND")
    te.add_argument("to")
    bk = sub.add_parser("backup", help="exporte toute la base dans un fichier .json.gz (sauvegarde portable)")
    bk.add_argument("--dir", default="backups")
    bk.add_argument("--keep", type=int, default=14, help="nombre de sauvegardes gardées")
    lk = sub.add_parser("check-links")
    lk.add_argument("--all", action="store_true", help="re-teste même les liens vérifiés récemment")
    args = parser.parse_args()

    if args.cmd == "seed":
        seed()
        return
    init_db()
    db = SessionLocal()
    try:
        if args.cmd == "collect":
            res = {args.source: run_source(db, args.source)} if args.source else run_all(db)
            for k, v in res.items():
                print(f"- {k} : {v}")
        elif args.cmd == "extract":
            f = PoliteFetcher(min_delay=0)
            try:
                rec = extract(f.get(args.url), args.url, use_ai=get_settings().ai_enabled)
            except RobotsDisallowed:
                print("robots.txt interdit la collecte de cette page : on ne la récupère pas.")
                return
            finally:
                f.close()
            print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
        elif args.cmd == "nightly":
            from .scheduler import run_cycle

            db.close()
            for k, v in run_cycle().items():
                print(f"- {k} : {v}")
        elif args.cmd == "discover":
            from .scrapers.collector import sync_sources
            from .scrapers.discovery import run_ai_discovery

            sync_sources(db)
            src = db.scalars(select(Source).where(Source.connector == "ai_discovery")).first()
            try:
                created, updated = run_ai_discovery(db, src, {"zones_per_run": args.zones})
            except RuntimeError as e:
                print(e)
                return
            print(f"{created} nouvelle(s) bourse(s), {updated} mise(s) à jour ")
        elif args.cmd == "translate":
            from .translate import load_seed_translations, translate_missing

            print(f"Fiches de départ : {load_seed_translations(db)} ; traduites par l'IA : {translate_missing(db, args.limit)}")
        elif args.cmd == "make-admin":
            from .models import User

            u = db.scalars(select(User).where(User.email == args.email.strip().lower())).first()
            if u is None:
                print("Aucun compte avec cette adresse : créez d'abord le compte sur le site.")
            else:
                u.is_admin = True
                u.email_verified = True
                db.commit()
                print(f"{u.email} est administrateur.")
        elif args.cmd == "check-config":
            from .launch import check_config

            problems = check_config(db)
            for level, msg in problems:
                print(f"[{level}] {msg}")
            print("Tout est prêt pour la mise en ligne." if not any(lv == "BLOQUANT" for lv, _ in problems) else "Corrigez les points BLOQUANT avant la mise en ligne.")
        elif args.cmd == "test-email":
            from .mailer import email_button, send_email

            ok = send_email(db, args.to, "E-mail d'essai ScholarFit",
                            "Bonjour,\n\nCet e-mail confirme que l'envoi depuis ScholarFit fonctionne.",
                            button=email_button("Ouvrir ScholarFit", "/"), kind="essai")
            db.commit()
            print("E-mail envoyé." if ok else "Échec de l'envoi : voir le message ci-dessus et les réglages EMAIL_* du fichier .env.")
        elif args.cmd == "backup":
            from .launch import backup

            print(f"Sauvegarde écrite : {backup(db, args.dir, args.keep)}")
        elif args.cmd == "check-links":
            from .linkcheck import broken, check_links

            print(check_links(db, max_age_days=0 if args.all else 7))
            for s in broken(db):
                print(f"  LIEN MORT : {s.title} → {s.official_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
