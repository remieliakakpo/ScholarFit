"""Tables de la base. Les listes (niveaux, pays, domaines…) sont stockées en JSON,
ce qui fonctionne aussi bien avec SQLite qu'avec PostgreSQL."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    method: Mapped[str] = mapped_column(String(20), default="page")  # api | rss | page | manual
    connector: Mapped[str] = mapped_column(String(50), default="manual")
    frequency_hours: Mapped[int] = mapped_column(Integer, default=24 * 7)
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    robots_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Scholarship(Base):
    __tablename__ = "scholarships"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    # Type d'opportunité : bourse | stage | conference (même fiche, même matching)
    kind: Mapped[str] = mapped_column(String(20), default="bourse", index=True)
    organization: Mapped[str] = mapped_column(String(300))
    official_url: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")

    levels: Mapped[list] = mapped_column(JSON, default=list)  # niveaux visés : BAC, BAC3, BAC5, BAC7
    study_countries: Mapped[list] = mapped_column(JSON, default=list)  # ISO2, vide = plusieurs pays
    eligible_nationalities: Mapped[list] = mapped_column(JSON, default=lambda: ["ALL"])  # ISO2 ou groupes
    excluded_nationalities: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=lambda: ["tous"])
    languages: Mapped[list] = mapped_column(JSON, default=list)  # fr, en, de…

    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount_period: Mapped[str | None] = mapped_column(String(20), nullable=True)  # mois | an | total
    coverage: Mapped[list] = mapped_column(JSON, default=list)  # frais, logement, voyage, allocation, assurance
    full_funding: Mapped[bool] = mapped_column(Boolean, default=False)

    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_grade: Mapped[float | None] = mapped_column(Float, nullable=True)  # sur 20
    requirements: Mapped[list] = mapped_column(JSON, default=list)  # cv, lettre, recommandation, releves, test_langue
    language_tests: Mapped[dict] = mapped_column(JSON, default=dict)  # {"IELTS": 6.5}
    target_groups: Mapped[list] = mapped_column(JSON, default=list)  # refugie, handicap, revenus_modestes, femmes

    # Fiche détaillée : conditions en phrases, précisions sur les pièces, étapes pour postuler
    eligibility: Mapped[list] = mapped_column(JSON, default=list)  # conditions propres à la bourse (en plus de celles déduites)
    documents_detail: Mapped[dict] = mapped_column(JSON, default=dict)  # {"recommandation": "2 lettres d'enseignants"}
    extra_documents: Mapped[list] = mapped_column(JSON, default=list)  # pièces hors liste standard, en clair
    apply_via: Mapped[str] = mapped_column(String(20), default="direct")  # direct | universite | ambassade | etablissement | nomination
    application_steps: Mapped[list] = mapped_column(JSON, default=list)  # étapes propres ; vide = étapes générées
    apply_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # portail de candidature si différent
    # Versions traduites des champs rédigés : {"en": {"title", "summary", "eligibility", "application_steps",
    # "documents_detail", "extra_documents", "duration", "hash"}} (voir app/translate.py)
    translations: Mapped[dict] = mapped_column(JSON, default=dict)

    # Vérification du lien officiel (app/linkcheck.py)
    link_status: Mapped[str] = mapped_column(String(20), default="non_verifie")  # ok | redirige | casse | non_verifie
    link_final_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Stages et conférences
    event_start: Mapped[date | None] = mapped_column(Date, nullable=True)  # début de la conférence (ou du stage)
    event_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)  # en ligne / à distance possible
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ex. « 3 à 6 mois »
    source_page: Mapped[str | None] = mapped_column(String(500), nullable=True)  # page de l'agrégateur où elle a été vue

    # Session passée d'une bourse annuelle (pour prévenir que la date est dépassée)
    previous_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_estimated: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | expiree | a_verifier
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Publication : « publie » (visible), « a_relire » (collectée automatiquement, attend une relecture
    # dans /admin), « rejete ». Les fiches de départ et celles saisies dans /admin sont publiées.
    review: Mapped[str] = mapped_column(String(12), default="publie", index=True)
    # Modifiée à la main dans /admin : le chargement des fiches de départ ne l'écrase plus.
    edited_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Années d'expérience professionnelle exigées (ex. Chevening 2, Banque mondiale 3)
    min_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Pièce rédigée attendue : lettre | essais | personal_statement | projet_recherche
    statement_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Langue(s) du dossier (codes ISO : fr, en, de…). Vide : déduite du pays.
    application_languages: Mapped[list] = mapped_column(JSON, default=list)

    source: Mapped[Source | None] = relationship()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    # Prénom ou nom d'utilisateur demandé à l'inscription (« Salut, Awa »). Vide pour les anciens comptes.
    name: Mapped[str] = mapped_column(String(80), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    lang: Mapped[str] = mapped_column(String(2), default="fr")  # langue choisie sur le site (alertes, e-mails)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications: Mapped[list["Application"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    advisor: Mapped["Advisor | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    coachings: Mapped[list["Coaching"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    doc_packs: Mapped[list["DocPack"]] = relationship(cascade="all, delete-orphan")
    credit_orders: Mapped[list["CreditOrder"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def is_advisor(self) -> bool:
        return self.advisor is not None and self.advisor.active

    @property
    def display_name(self) -> str:
        """Nom affiché dans « Salut, … » : nom d'utilisateur, sinon prénom du profil, sinon début de l'e-mail."""
        if self.name and self.name.strip():
            return self.name.strip()
        full = (self.profile.full_name or "").strip() if self.profile else ""
        if full:
            return full.split()[0]
        return self.email.split("@")[0]


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # Étape 1 : identité
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nationalities: Mapped[list] = mapped_column(JSON, default=list)
    residence_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    alerts_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)

    # Étape 2 : parcours
    current_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grade_average: Mapped[float | None] = mapped_column(Float, nullable=True)  # sur 20
    diplomas: Mapped[list] = mapped_column(JSON, default=list)

    # Étape 3 : projet et atouts
    wished_countries: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[dict] = mapped_column(JSON, default=dict)  # {"fr": "natif", "en": "B2"}
    language_scores: Mapped[dict] = mapped_column(JSON, default=dict)  # {"IELTS": 6.5}
    experiences: Mapped[str | None] = mapped_column(Text, nullable=True)
    engagement: Mapped[str | None] = mapped_column(Text, nullable=True)
    interests: Mapped[str | None] = mapped_column(Text, nullable=True)  # centres d'intérêt (rubrique du CV)
    work_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)  # années d'expérience professionnelle
    project: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_funding_only: Mapped[bool] = mapped_column(Boolean, default=False)
    wished_regions: Mapped[list] = mapped_column(JSON, default=list)  # afrique, europe, amerique, asie, oceanie (vide = partout)
    # Étape 5 du questionnaire : postuler seul ou être accompagné
    help_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)  # seul | standard | premium | ne_sait_pas
    applications_planned: Mapped[int | None] = mapped_column(Integer, nullable=True)  # nombre de bourses visées
    questionnaire_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Facultatif (sensible) : débloque des bourses ciblées
    situations: Mapped[list] = mapped_column(JSON, default=list)  # refugie, handicap, revenus_modestes, premiere_generation, femmes

    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # En-tête des CV et lettres
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    links: Mapped[str | None] = mapped_column(String(300), nullable=True)  # LinkedIn, portfolio…
    # Accords grammaticaux des lettres en français : f | m (vide = tournures neutres)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "scholarship_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scholarship_id: Mapped[int] = mapped_column(ForeignKey("scholarships.id"))
    # a_preparer | en_cours | envoyee | acceptee | refusee
    status: Mapped[str] = mapped_column(String(20), default="a_preparer")
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)  # {"cv": true, "lettre": false}
    letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="applications")
    scholarship: Mapped[Scholarship] = relationship()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))  # cv_original | cv_ameliore | cv_adapte | lettre
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    scholarship_id: Mapped[int | None] = mapped_column(ForeignKey("scholarships.id"), nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # version structurée (CV ou lettre)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="documents")


class Alert(Base):
    """Notifications générées (nouvelle bourse, rappel de date limite).
    Le MVP les affiche dans l'interface et les écrit dans la console ; l'envoi par
    e-mail ou WhatsApp se branche dans app/alerts.py."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(100))  # évite les doublons, ex. "rappel-12-J7"
    kind: Mapped[str] = mapped_column(String(30))  # nouvelle_bourse | rappel
    message: Mapped[str] = mapped_column(Text)
    scholarship_id: Mapped[int | None] = mapped_column(ForeignKey("scholarships.id"), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="alerts")


class AIUsage(Base):
    """Compteur de générations IA par jour, pour maîtriser les coûts."""

    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)


# ---------- Accompagnement des candidatures ----------
class Advisor(Base):
    """Conseiller ou conseillère qui accompagne des candidats (ancien boursier, enseignant, bénévole…)."""

    __tablename__ = "advisors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str] = mapped_column(Text, default="")
    levels: Mapped[list] = mapped_column(JSON, default=list)  # BAC, BAC3, BAC5, BAC7 (vide = tous)
    countries: Mapped[list] = mapped_column(JSON, default=list)  # pays d'études connus (ISO2)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["fr"])
    capacity: Mapped[int] = mapped_column(Integer, default=5)  # candidats suivis en même temps
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="advisor")
    coachings: Mapped[list["Coaching"]] = relationship(back_populates="advisor")


class Coaching(Base):
    """Un accompagnement : demande du candidat, attribution à un conseiller, puis suivi."""

    __tablename__ = "coachings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[int | None] = mapped_column(ForeignKey("advisors.id", ondelete="SET NULL"), nullable=True, index=True)
    # demande | en_cours | termine | annule
    status: Mapped[str] = mapped_column(String(20), default="demande")
    goal: Mapped[str] = mapped_column(Text)
    needs: Mapped[list] = mapped_column(JSON, default=list)  # choix_bourses, cv, lettre, recommandations, entretien, visa
    application_ids: Mapped[list] = mapped_column(JSON, default=list)  # candidatures du suivi concernées
    preferred_language: Mapped[str] = mapped_column(String(10), default="fr")
    offer: Mapped[str] = mapped_column(String(20), default="standard")  # standard | premium
    price: Mapped[int] = mapped_column(Integer, default=0)  # en F CFA, figé au moment de la demande
    currency: Mapped[str] = mapped_column(String(5), default="XOF")
    payment_status: Mapped[str] = mapped_column(String(20), default="a_payer")  # a_payer | paye | offert | rembourse
    availability: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 à 5, à la fin
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student: Mapped[User] = relationship(back_populates="coachings")
    advisor: Mapped[Advisor | None] = relationship(back_populates="coachings")
    steps: Mapped[list["CoachingStep"]] = relationship(
        back_populates="coaching", cascade="all, delete-orphan", order_by="CoachingStep.position"
    )
    messages: Mapped[list["CoachingMessage"]] = relationship(
        back_populates="coaching", cascade="all, delete-orphan", order_by="CoachingMessage.created_at"
    )
    meetings: Mapped[list["CoachingMeeting"]] = relationship(
        back_populates="coaching", cascade="all, delete-orphan", order_by="CoachingMeeting.starts_at"
    )


class CoachingStep(Base):
    """Étape du plan d'accompagnement (ex. « Faire relire la lettre »), avec une échéance."""

    __tablename__ = "coaching_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    coaching_id: Mapped[int] = mapped_column(ForeignKey("coachings.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    coaching: Mapped[Coaching] = relationship(back_populates="steps")


class CoachingMessage(Base):
    __tablename__ = "coaching_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    coaching_id: Mapped[int] = mapped_column(ForeignKey("coachings.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_role: Mapped[str] = mapped_column(String(20))  # candidat | conseiller | admin
    content: Mapped[str] = mapped_column(Text)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # message sur une candidature
    read_by_student: Mapped[bool] = mapped_column(Boolean, default=False)
    read_by_advisor: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    coaching: Mapped[Coaching] = relationship(back_populates="messages")


class CoachingMeeting(Base):
    """Rendez-vous (visio, téléphone, sur place), proposé par l'un, confirmé par l'autre."""

    __tablename__ = "coaching_meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    coaching_id: Mapped[int] = mapped_column(ForeignKey("coachings.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    mode: Mapped[str] = mapped_column(String(20), default="visio")  # visio | telephone | sur_place
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # propose | confirme | annule | fait
    status: Mapped[str] = mapped_column(String(20), default="propose")
    proposed_by: Mapped[str] = mapped_column(String(20))  # candidat | conseiller
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # compte rendu après le rendez-vous
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    coaching: Mapped[Coaching] = relationship(back_populates="meetings")


class DocPack(Base):
    """Un « dossier » : un CV adapté et une lettre pour une bourse donnée.

    Le premier dossier est offert ; les suivants sont compris dans l'abonnement mensuel
    (SUBSCRIPTION_PRICE, 2 500 F CFA par mois, jusqu'à SUBSCRIPTION_MONTHLY_PACKS dossiers par mois).
    Dans un dossier, l'étudiant peut relancer la génération quelques fois (DOC_PACK_REGENERATIONS)
    et modifier les textes librement.
    """

    __tablename__ = "doc_packs"
    __table_args__ = (UniqueConstraint("user_id", "scholarship_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scholarship_id: Mapped[int | None] = mapped_column(ForeignKey("scholarships.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="offert")  # offert | abonnement | achat (ancien modèle)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("credit_orders.id"), nullable=True)
    cv_runs: Mapped[int] = mapped_column(Integer, default=0)
    letter_runs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scholarship: Mapped[Scholarship | None] = relationship()


class CreditOrder(Base):
    """Paiement d'un mois d'abonnement, réglé par Mobile Money ou transfert puis validé par un administrateur.

    Chaque paiement validé ouvre (ou prolonge) l'abonnement de SUBSCRIPTION_DAYS jours."""

    __tablename__ = "credit_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="XOF")
    method: Mapped[str] = mapped_column(String(30))  # flooz | mixx | taptap_send | lemfi | pi_spi
    payer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # en_verification | paye | refuse
    status: Mapped[str] = mapped_column(String(20), default="en_verification")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="credit_orders")


class Payment(Base):
    """Paiement en ligne (CinetPay, ou simulation pour les essais).

    purpose = abonnement : un mois d'abonnement CV et lettres. Une fois payé, un CreditOrder « payé »
    est créé, ce qui ouvre ou prolonge l'abonnement comme une validation manuelle.
    purpose = accompagnement : règle l'offre Standard ou Premium d'un accompagnement (coaching_id)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # abonnement | accompagnement
    coaching_id: Mapped[int | None] = mapped_column(ForeignKey("coachings.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(5), default="XOF")
    description: Mapped[str] = mapped_column(String(200), default="")
    provider: Mapped[str] = mapped_column(String(20))  # cinetpay | simulation
    # en_attente | paye | echoue | annule
    status: Mapped[str] = mapped_column(String(20), default="en_attente", index=True)
    checkout_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # moyen utilisé (FLOOZ, TMONEY, VISA…)
    provider_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    credit_order_id: Mapped[int | None] = mapped_column(ForeignKey("credit_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


class EmailLog(Base):
    """Trace de chaque e-mail envoyé (ou affiché en console), pour l'administration et pour éviter les doublons."""

    __tablename__ = "email_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    to: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(40), default="autre")  # rappel | bienvenue | paiement | message | verification…
    key: Mapped[str | None] = mapped_column(String(150), nullable=True, unique=True)  # envoi unique (ex. rappel-12-J7-user3)
    backend: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="envoye")  # envoye | echec
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CoachingFile(Base):
    """Document échangé dans un accompagnement : livré par l'expert (CV revu, lettre, preuve de dépôt)
    ou envoyé par le candidat (relevés, diplômes…). Gardé en base pour simplifier les sauvegardes."""

    __tablename__ = "coaching_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    coaching_id: Mapped[int] = mapped_column(ForeignKey("coachings.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_role: Mapped[str] = mapped_column(String(20))  # candidat | conseiller | admin
    # livrable | piece | preuve_depot
    category: Mapped[str] = mapped_column(String(20), default="piece")
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """Réglages gardés en base (ex. clé de signature générée quand SECRET_KEY n'est pas fournie)."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
