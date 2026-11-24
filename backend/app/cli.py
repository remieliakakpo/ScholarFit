"""Commandes d'administration.

    python -m app.cli seed            # met la base à jour, charge les données d'exemple (+ comptes de démo si APP_ENV=dev)
    python -m app.cli create-admin EMAIL   # crée ou promeut un administrateur (mot de passe demandé ou tiré au hasard)
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
import getpass
import sys
import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal, init_db
from .models import Advisor, Application, Profile, Scholarship, Source, User
from .scrapers.base import PoliteFetcher, RobotsDisallowed
from .scrapers.collector import run_all, run_source
from .scrapers.extract import extract
from .security import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEMO_PASSWORD = "demo12345"


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        print(run_source(db, "Données d'exemple"))
        from .translate import load_seed_translations

        print(f"Version anglaise : {load_seed_translations(db)} fiche(s)")
        if not get_settings().is_dev:
            # En production, aucun compte à mot de passe connu : python -m app.cli create-admin EMAIL
            db.commit()
            return
        verified = datetime.now(timezone.utc)
        admin_email = get_settings().admin_email_list[0]
        if not db.scalars(select(User).where(User.email == admin_email)).first():
            db.add(User(email=admin_email, password_hash=hash_password("admin12345"), is_admin=True, profile=Profile(),
                        email_verified_at=verified, terms_accepted_at=verified))
            print(f"Compte admin : {admin_email} / admin12345")
        demo = db.scalars(select(User).where(User.email == "demo@example.org")).first()
        if not demo:
            demo = User(email="demo@example.org", password_hash=hash_password(DEMO_PASSWORD),
                        email_verified_at=verified, terms_accepted_at=verified)
            demo.profile = Profile(
                full_name="Awa Diop", birth_date=date(date.today().year - 22, 4, 12), nationalities=["SN"],
                residence_country="SN", current_level="BAC3", target_level="BAC5", domain="informatique",
                institution="Université Cheikh Anta Diop de Dakar", grade_average=15.2,
                wished_countries=["FR", "CA", "DE"], languages={"fr": "natif", "en": "B2", "wo": "natif"},
                language_scores={"IELTS": 6.5}, experiences="Stage de 3 mois en développement web chez une start-up de Dakar.\nTutorat en programmation pour 25 étudiants de L1.",
                engagement="Membre fondatrice du club de robotique de la faculté (40 membres).",
                project="Devenir ingénieure en intelligence artificielle appliquée à la santé et à l'agriculture au Sénégal.",
            )
            db.add(demo)
            db.flush()
            first = db.scalars(select(Scholarship).where(Scholarship.title.like("%Eiffel%"))).first()
            if first:
                db.add(Application(user_id=demo.id, scholarship_id=first.id, status="en_cours",
                                   checklist={r: r == "cv" for r in first.requirements}))
            print(f"Compte de démo : demo@example.org / {DEMO_PASSWORD}")
        if not db.scalars(select(User).where(User.email == "conseiller@example.org")).first():
            db.add(User(
                email="conseiller@example.org", password_hash=hash_password("conseil12345"), profile=Profile(full_name="Moussa Ndiaye"),
                email_verified_at=verified, terms_accepted_at=verified,
                advisor=Advisor(
                    display_name="Moussa Ndiaye",
                    bio="Ancien boursier Eiffel (master en informatique à Paris), j'aide les candidats à choisir leurs bourses et à soigner leur dossier.",
                    levels=["BAC3", "BAC5", "BAC7"], countries=["FR", "CA", "BE"], domains=["informatique", "ingenierie", "mathematiques"],
                    languages=["fr", "en"], capacity=10,
                ),
            ))
            print("Compte conseiller : conseiller@example.org / conseil12345")
        db.commit()
    finally:
        db.close()


def create_admin(email: str, password: str | None) -> None:
    from .security import password_problem

    init_db()
    email = email.strip().lower()
    shown = None
    if password is None:
        typed = getpass.getpass("Mot de passe (vide = tiré au hasard) : ") if sys.stdin.isatty() else ""
        password = typed or secrets.token_urlsafe(14)
        shown = None if typed else password
    problem = password_problem(password, email)
    if problem:
        raise SystemExit(problem)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user = db.scalars(select(User).where(User.email == email)).first()
        if user is None:
            user = User(email=email, profile=Profile(), terms_accepted_at=now)
            db.add(user)
        user.password_hash = hash_password(password)
        user.is_admin = True
        user.email_verified_at = user.email_verified_at or now
        user.token_version = (user.token_version or 0) + 1
        db.commit()
        print(f"Administrateur prêt : {email}")
        if shown:
            print(f"Mot de passe (affiché une seule fois, changez-le après connexion) : {shown}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    ca = sub.add_parser("create-admin", help="crée ou promeut un compte administrateur")
    ca.add_argument("email")
    ca.add_argument("--password", help="sinon demandé, ou tiré au hasard et affiché une fois")
    c = sub.add_parser("collect")
    c.add_argument("--source")
    e = sub.add_parser("extract")
    e.add_argument("url")
    sub.add_parser("nightly")
    d = sub.add_parser("discover")
    d.add_argument("--zones", type=int, default=5, help="nombre de zones du monde à parcourir (46 au total)")
    tr = sub.add_parser("translate", help="version anglaise des fiches qui n'en ont pas (IA)")
    tr.add_argument("--limit", type=int, default=500)
    lk = sub.add_parser("check-links")
    lk.add_argument("--all", action="store_true", help="re-teste même les liens vérifiés récemment")
    args = parser.parse_args()

    if args.cmd == "seed":
        seed()
        return
    if args.cmd == "create-admin":
        create_admin(args.email, args.password)
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
        elif args.cmd == "check-links":
            from .linkcheck import broken, check_links

            print(check_links(db, max_age_days=0 if args.all else 7))
            for s in broken(db):
                print(f"  LIEN MORT : {s.title} → {s.official_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
