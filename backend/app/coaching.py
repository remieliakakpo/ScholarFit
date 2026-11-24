"""Accompagnement des candidatures par un conseiller.

Parcours : le candidat fait une demande (objectif, besoins, candidatures concernées, accord
de partage du dossier) -> un conseiller lui est attribué (automatiquement si l'option est
active, sinon par un administrateur) -> un plan d'étapes daté est créé à partir des dates
limites de ses candidatures -> échanges par messages et rendez-vous -> fin et avis.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .alerts import _add
from .models import Advisor, Application, Coaching, CoachingMeeting, CoachingStep, User

ACTIVE = ("demande", "en_cours")
STATUSES = {"demande": "En attente d'un conseiller", "en_cours": "En cours", "termine": "Terminé", "annule": "Annulé"}
NEEDS = {
    "choix_bourses": "Choisir les bonnes bourses",
    "cv": "Relecture du CV",
    "lettre": "Relecture de la lettre de motivation",
    "recommandations": "Lettres de recommandation",
    "entretien": "Préparer l'entretien",
    "langue": "Test de langue",
    "visa": "Visa et installation",
}
MEETING_MODES = {"visio": "Visio", "telephone": "Téléphone", "sur_place": "Sur place"}
MEETING_STATUSES = {"propose": "Proposé", "confirme": "Confirmé", "annule": "Annulé", "fait": "Fait"}


def load(db: Session, advisor: Advisor) -> int:
    return db.scalar(
        select(func.count()).select_from(Coaching).where(Coaching.advisor_id == advisor.id, Coaching.status == "en_cours")
    ) or 0


def advisor_fit(advisor: Advisor, coaching: Coaching) -> int:
    """Score d'adéquation conseiller / candidat (plus c'est haut, mieux c'est)."""
    p = coaching.student.profile
    score = 0
    if coaching.preferred_language in (advisor.languages or []):
        score += 30
    if p is not None:
        if p.target_level and (not advisor.levels or p.target_level in advisor.levels):
            score += 20
        if p.domain and p.domain in (advisor.domains or []):
            score += 20
        if set(p.wished_countries or []) & set(advisor.countries or []):
            score += 20
    countries = {c for a in coaching.student.applications if a.id in (coaching.application_ids or []) for c in a.scholarship.study_countries or []}
    if countries & set(advisor.countries or []):
        score += 10
    return score


def suggest_advisors(db: Session, coaching: Coaching, limit: int = 3) -> list[tuple[Advisor, int]]:
    """Conseillers actifs qui ont encore de la place, du plus adapté au moins adapté."""
    out = []
    for a in db.scalars(select(Advisor).where(Advisor.active.is_(True))):
        if a.user_id == coaching.student_id:
            continue
        n = load(db, a)
        if n >= a.capacity:
            continue
        out.append((a, n, advisor_fit(a, coaching)))
    out.sort(key=lambda t: (-t[2], t[1], t[0].id))
    return [(a, n) for a, n, _ in out[:limit]]


def default_plan(coaching: Coaching, today: date | None = None) -> list[CoachingStep]:
    """Plan type, daté à rebours depuis la date limite la plus proche des candidatures concernées."""
    today = today or date.today()
    apps = [a for a in coaching.student.applications if a.id in (coaching.application_ids or [])]
    deadlines = sorted(a.scholarship.deadline for a in apps if a.scholarship.deadline and a.scholarship.deadline >= today)
    deadline = deadlines[0] if deadlines else today + timedelta(days=60)
    needs = set(coaching.needs or [])

    def at(days_before: int, minimum: int) -> date:
        return max(deadline - timedelta(days=days_before), today + timedelta(days=minimum))

    plan: list[tuple[str, str, date]] = [
        ("Premier rendez-vous avec votre conseiller", "Faire le point sur votre projet, vos bourses visées et votre calendrier.", today + timedelta(days=7)),
        ("Compléter votre profil", "Un profil complet donne de meilleurs résultats de matching et aide votre conseiller.", today + timedelta(days=10)),
    ]
    if not apps or "choix_bourses" in needs:
        plan.append(("Choisir les bourses avec votre expert", "Une bourse en Standard, trois en Premium, à ajouter au suivi depuis « Mes bourses ».", at(45, 14)))
    if "langue" in needs:
        plan.append(("Passer ou planifier le test de langue", "Vérifier le score exigé et les dates de session.", at(40, 14)))
    plan.append(("Faire relire votre CV", "Partager la version améliorée avec votre conseiller.", at(30, 14)))
    if "recommandations" in needs or any("recommandation" in (a.scholarship.requirements or []) for a in apps):
        plan.append(("Demander les lettres de recommandation", "Prévenir vos professeurs au moins 3 semaines avant la date limite.", at(28, 14)))
    plan.append(("Faire relire votre lettre de motivation", "Une lettre par bourse, adaptée à son programme.", at(21, 18)))
    plan.append(("Vérification finale et dépôt par votre expert", "Votre expert vérifie toutes les pièces, dépose la candidature avant la date limite et vous transmet la preuve de dépôt.", at(3, 21)))
    if "entretien" in needs:
        plan.append(("Préparer l'entretien", "Simulation avec votre conseiller : présentation, projet, questions fréquentes.", at(-14, 28)))
    if "visa" in needs:
        plan.append(("Préparer le visa et l'installation", "Liste des pièces, logement, assurance.", at(-30, 35)))
    plan.sort(key=lambda t: t[2])
    return [CoachingStep(position=i, title=t, description=d, due_date=due) for i, (t, d, due) in enumerate(plan)]


def notify(db: Session, user: User, key: str, message: str) -> None:
    _add(db, user, key, "accompagnement", message, None)


def assign(db: Session, coaching: Coaching, advisor: Advisor) -> None:
    first = coaching.advisor_id is None
    coaching.advisor = advisor
    coaching.status = "en_cours"
    coaching.assigned_at = datetime.now(timezone.utc)
    if first and not coaching.steps:
        coaching.steps = default_plan(coaching)
    db.flush()
    notify(db, coaching.student, f"acc-{coaching.id}-attribue-{advisor.id}",
           f"{advisor.display_name} va vous accompagner dans vos candidatures. Votre plan d'étapes est prêt.")
    p = coaching.student.profile
    name = p.full_name if p is not None and p.full_name else coaching.student.email
    notify(db, advisor.user, f"acc-{coaching.id}-nouveau-{advisor.id}", f"Nouveau candidat à accompagner : {name}.")


def run_reminders(db: Session, today: date | None = None) -> int:
    """Rappels de la veille : étapes à échéance et rendez-vous confirmés du lendemain."""
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    created = 0
    for c in db.scalars(select(Coaching).where(Coaching.status == "en_cours")):
        for s in c.steps:
            if not s.done and s.due_date == tomorrow:
                created += _add(db, c.student, f"acc-etape-{s.id}-J1", "accompagnement", f"Étape à terminer demain : « {s.title} ».", None)
        for m in c.meetings:
            start = m.starts_at if m.starts_at.tzinfo else m.starts_at.replace(tzinfo=timezone.utc)
            if m.status == "confirme" and start.date() == tomorrow:
                msg = f"Rendez-vous d'accompagnement demain à {start:%H:%M} (UTC) : {m.topic or 'point d’étape'}."
                created += _add(db, c.student, f"acc-rdv-{m.id}-J1", "accompagnement", msg, None)
                if c.advisor:
                    created += _add(db, c.advisor.user, f"acc-rdv-{m.id}-J1", "accompagnement", msg, None)
    db.commit()
    return created


def linked_applications(coaching: Coaching) -> list[Application]:
    ids = set(coaching.application_ids or [])
    return [a for a in coaching.student.applications if not ids or a.id in ids]


def next_meeting(coaching: Coaching) -> CoachingMeeting | None:
    now = datetime.now(timezone.utc)
    upcoming = [m for m in coaching.meetings if m.status in ("propose", "confirme")
                and (m.starts_at if m.starts_at.tzinfo else m.starts_at.replace(tzinfo=timezone.utc)) >= now]
    return upcoming[0] if upcoming else None
