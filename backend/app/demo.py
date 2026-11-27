"""Comptes de démonstration documentés dans le README.

Ils sont créés (ou réparés si leur mot de passe a changé) par « python -m app.cli seed » et à chaque
démarrage de l'API tant que DEMO_ACCOUNTS=true : les identifiants du README marchent donc toujours,
même si l'API a été lancée sans passer par start.ps1 ou si ADMIN_EMAILS contient une autre adresse.
En production, mettez DEMO_ACCOUNTS=false une fois vos vrais comptes créés.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Advisor, Application, Profile, Scholarship, User
from .security import hash_password, verify_password

log = logging.getLogger("demo")

DEMO_ADMIN = ("admin@example.org", "admin12345")
DEMO_STUDENT = ("demo@example.org", "demo12345")
DEMO_ADVISOR = ("conseiller@example.org", "conseil12345")


def _ensure(db: Session, email: str, password: str, name: str) -> tuple[User, bool]:
    """Compte présent avec ce mot de passe ; renvoie (compte, créé ?)."""
    user = db.scalars(select(User).where(User.email == email)).first()
    created = user is None
    if created:
        user = User(email=email, password_hash=hash_password(password), name=name, email_verified=True)
        db.add(user)
    else:
        if not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
            log.warning("Mot de passe du compte de démo %s remis à celui du README", email)
        if not user.name:
            user.name = name
        user.email_verified = True
    return user, created


def ensure_demo_accounts(db: Session, verbose: bool = False) -> None:
    say = print if verbose else log.info

    admin, created = _ensure(db, *DEMO_ADMIN, name="Admin")
    admin.is_admin = True
    if admin.profile is None:
        admin.profile = Profile()

    demo, created = _ensure(db, *DEMO_STUDENT, name="Awa")
    if demo.profile is None:
        demo.profile = Profile(
            full_name="Awa Diop", birth_date=date(date.today().year - 22, 4, 12), nationalities=["SN"],
            residence_country="SN", current_level="BAC3", target_level="BAC5", domain="informatique",
            institution="Université Cheikh Anta Diop de Dakar", grade_average=15.2,
            wished_countries=["FR", "CA", "DE"], languages={"fr": "natif", "en": "B2", "wo": "natif"},
            language_scores={"IELTS": 6.5}, experiences="Stage de 3 mois en développement web chez une start-up de Dakar.\nTutorat en programmation pour 25 étudiants de L1.",
            engagement="Membre fondatrice du club de robotique de la faculté (40 membres).",
            project="Devenir ingénieure en intelligence artificielle appliquée à la santé et à l'agriculture au Sénégal.",
        )
    if created:
        db.flush()
        first = db.scalars(select(Scholarship).where(Scholarship.title.like("%Eiffel%"))).first()
        if first:
            db.add(Application(user_id=demo.id, scholarship_id=first.id, status="en_cours",
                               checklist={r: r == "cv" for r in first.requirements}))

    adv, created = _ensure(db, *DEMO_ADVISOR, name="Moussa")
    if adv.profile is None:
        adv.profile = Profile(full_name="Moussa Ndiaye")
    if adv.advisor is None:
        adv.advisor = Advisor(
            display_name="Moussa Ndiaye",
            bio="Ancien boursier Eiffel (master en informatique à Paris), j'aide les candidats à choisir leurs bourses et à soigner leur dossier.",
            levels=["BAC3", "BAC5", "BAC7"], countries=["FR", "CA", "BE"], domains=["informatique", "ingenierie", "mathematiques"],
            languages=["fr", "en"], capacity=10,
        )
    db.commit()
    say("Comptes de démo prêts : "
        f"{DEMO_STUDENT[0]} / {DEMO_STUDENT[1]} (étudiante), {DEMO_ADMIN[0]} / {DEMO_ADMIN[1]} (admin), "
        f"{DEMO_ADVISOR[0]} / {DEMO_ADVISOR[1]} (conseiller)")
