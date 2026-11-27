from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .vocab import DOMAINS, KINDS, LEVELS


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Comptes ----------
class RegisterIn(BaseModel):
    # demandé par le formulaire d'inscription ; facultatif pour l'API (sinon début de l'e-mail)
    name: str = Field(default="", max_length=80)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    home: str = "/mes-bourses"  # page d'arrivée après connexion selon le rôle


class UserOut(ORM):
    id: int
    email: str
    name: str = ""
    display_name: str = ""
    email_verified: bool = False
    is_admin: bool
    is_advisor: bool = False


class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    password: str = Field(min_length=8)


# ---------- Bourses ----------
class ScholarshipBase(BaseModel):
    kind: str = "bourse"  # bourse | stage | conference
    title: str
    organization: str
    official_url: str
    summary: str = ""
    levels: list[str] = []
    study_countries: list[str] = []
    eligible_nationalities: list[str] = ["ALL"]
    excluded_nationalities: list[str] = []
    domains: list[str] = ["tous"]
    languages: list[str] = []
    amount: float | None = None
    currency: str | None = None
    amount_period: str | None = None
    coverage: list[str] = []
    full_funding: bool = False
    deadline: date | None = None
    recurring: bool = True
    max_age: int | None = None
    min_grade: float | None = None
    requirements: list[str] = []
    language_tests: dict[str, float] = {}
    target_groups: list[str] = []
    status: str = "active"
    eligibility: list[str] = []  # conditions propres à la bourse, en phrases
    documents_detail: dict[str, str] = {}
    extra_documents: list[str] = []
    apply_via: str = "direct"  # direct | universite | ambassade | etablissement | nomination
    application_steps: list[str] = []  # en sortie : étapes propres ou générées
    apply_url: str | None = None
    event_start: date | None = None
    event_end: date | None = None
    city: str | None = None
    remote: bool = False
    duration: str | None = None
    min_experience_years: float | None = None
    statement_type: str | None = None  # lettre | essais | personal_statement | projet_recherche
    application_languages: list[str] = []

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"Type inconnu : {v}")
        return v

    @field_validator("levels")
    @classmethod
    def _levels(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in LEVELS]
        if bad:
            raise ValueError(f"Niveaux inconnus : {bad}")
        return v

    @field_validator("domains")
    @classmethod
    def _domains(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in DOMAINS]
        if bad:
            raise ValueError(f"Domaines inconnus : {bad}")
        return v


class ScholarshipIn(ScholarshipBase):
    pass


class DocumentItem(BaseModel):
    code: str
    label: str
    detail: str


class ScholarshipOut(ScholarshipBase, ORM):
    id: int
    slug: str
    collected_at: datetime
    verified_at: datetime | None = None
    source_name: str | None = None
    # Calculés pour l'affichage
    kind_label: str = ""
    source_page: str | None = None
    eligibility_notes: list[str] = []
    documents: list[DocumentItem] = []
    regions: list[str] = []
    link_status: str = "non_verifie"  # ok | redirige | casse | non_verifie
    link_checked_at: datetime | None = None
    deadline_status: str = "inconnue"  # ouverte | bientot | urgente | expiree | inconnue
    priority: int = 4  # 1 urgente, 2 bientôt, 3 ouverte, 4 inconnue, 5 expirée
    days_left: int | None = None
    deadline_label: str = ""
    deadline_estimated: bool = False
    previous_deadline: date | None = None
    next_expected_deadline: date | None = None
    review: str = "publie"  # publie | a_relire | rejete


class ScholarshipPage(BaseModel):
    total: int
    items: list[ScholarshipOut]


# ---------- Profil ----------
class ProfileIn(BaseModel):
    full_name: str | None = None
    birth_date: date | None = None
    nationalities: list[str] | None = None
    residence_country: str | None = None
    phone: str | None = None
    alerts_opt_in: bool | None = None
    current_level: str | None = None
    target_level: str | None = None
    domain: str | None = None
    institution: str | None = None
    grade_average: float | None = Field(default=None, ge=0, le=20)
    diplomas: list[str] | None = None
    wished_countries: list[str] | None = None
    languages: dict[str, str] | None = None
    language_scores: dict[str, float] | None = None
    experiences: str | None = None
    engagement: str | None = None
    interests: str | None = None
    work_experience_years: float | None = Field(default=None, ge=0, le=60)
    project: str | None = None
    full_funding_only: bool | None = None
    situations: list[str] | None = None
    wished_regions: list[str] | None = None
    help_preference: str | None = None
    applications_planned: int | None = Field(default=None, ge=1, le=50)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    links: str | None = Field(default=None, max_length=300)
    gender: str | None = Field(default=None, pattern="^(|f|m)$")


class ProfileOut(ORM):
    full_name: str | None
    birth_date: date | None
    nationalities: list[str]
    residence_country: str | None
    phone: str | None
    alerts_opt_in: bool
    current_level: str | None
    target_level: str | None
    domain: str | None
    institution: str | None
    grade_average: float | None
    diplomas: list[str]
    wished_countries: list[str]
    languages: dict[str, str]
    language_scores: dict[str, float]
    experiences: str | None
    engagement: str | None
    interests: str | None = None
    work_experience_years: float | None = None
    project: str | None
    full_funding_only: bool
    situations: list[str]
    wished_regions: list[str] = []
    help_preference: str | None = None
    applications_planned: int | None = None
    questionnaire_done_at: datetime | None = None
    cv_text: str | None = None
    city: str | None = None
    address: str | None = None
    links: str | None = None
    gender: str | None = None
    has_cv: bool = False
    completeness: int = 0
    minimum_ok: bool = False
    missing_minimum: list[str] = []
    completeness_tip: str | None = None


# ---------- Matching ----------
class MatchOut(BaseModel):
    scholarship: ScholarshipOut
    score: int | None  # null sans compte : le score est réservé aux inscrits
    chance: str | None  # faible | moyenne | bonne
    reasons: list[str]
    gaps: list[str]
    days_left: int | None
    # Questionnaire : la bourse se trouve-t-elle dans les pays ou continents choisis ? (None = aucun choix)
    in_destination: bool | None = None


class MatchesOut(BaseModel):
    minimum_ok: bool
    missing_minimum: list[str]
    excluded_count: int
    items: list[MatchOut]
    # Bourses annuelles à session close qui conviendraient : « À préparer pour la prochaine session »
    next_session: list[MatchOut] = []
    # Conseil quand il y a peu de résultats (élargir les pays, compléter le profil)
    widen_hint: str | None = None


# ---------- Chat ----------
class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]
    criteria: dict = {}


class QuickReply(BaseModel):
    label: str
    value: str


class ChatOut(BaseModel):
    reply: str
    criteria: dict
    missing: list[str]
    quick_replies: list[QuickReply] = []
    results: list[MatchOut] = []
    ai_used: bool = False


# ---------- Candidatures (Kanban) ----------
class ApplicationIn(BaseModel):
    scholarship_id: int


class ApplicationUpdate(BaseModel):
    status: str | None = None
    checklist: dict[str, bool] | None = None
    notes: str | None = None
    letter: str | None = None


class ApplicationOut(ORM):
    id: int
    status: str
    checklist: dict[str, bool]
    notes: str | None
    letter: str | None
    created_at: datetime
    updated_at: datetime
    scholarship: ScholarshipOut


# ---------- IA : CV et lettres ----------
class CVTextIn(BaseModel):
    text: str = Field(min_length=30)
    scholarship_id: int | None = None
    target_format: str = "francais"  # francais | europass | us_resume | lebenslauf | academique


class CVIssue(BaseModel):
    category: str
    message: str


class CVRewrite(BaseModel):
    original: str
    proposal: str
    why: str


class CVReviewOut(BaseModel):
    score: int
    scores: dict[str, int]
    sections: dict[str, str]
    issues: list[CVIssue]
    rewrites: list[CVRewrite]
    format_tips: list[str]
    ai_used: bool


class LetterIn(BaseModel):
    scholarship_id: int
    why_country: str = ""
    why_program: str = ""
    project_after: str = ""
    proud_of: str = ""
    language: str = "fr"
    max_words: int = Field(default=500, ge=150, le=1200)
    tone: str = "sobre"  # sobre | chaleureux | dynamique


class LetterOut(BaseModel):
    letter: str
    word_count: int
    warnings: list[str]
    ai_used: bool


class DocCheckOut(BaseModel):
    ok: bool
    items: list[dict]


class AlertOut(ORM):
    id: int
    kind: str
    message: str
    scholarship_id: int | None
    read: bool
    created_at: datetime


class SourceOut(ORM):
    id: int
    name: str
    url: str
    method: str
    connector: str
    robots_allowed: bool | None
    last_run_at: datetime | None
    last_status: str | None
    enabled: bool


# ---------- Accompagnement ----------
class CoachingRequestIn(BaseModel):
    goal: str = Field(min_length=10, max_length=3000)
    needs: list[str] = []
    application_ids: list[int] = []
    preferred_language: str = "fr"
    availability: str | None = Field(default=None, max_length=1000)
    share_consent: bool
    offer: str = "standard"  # standard | premium


class PaymentIn(BaseModel):
    payment_status: str  # a_payer | paye | offert | rembourse


class AdvisorPublic(ORM):
    id: int
    display_name: str
    bio: str
    levels: list[str]
    countries: list[str]
    domains: list[str]
    languages: list[str]


class AdvisorIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=200)
    bio: str = ""
    levels: list[str] = []
    countries: list[str] = []
    domains: list[str] = []
    languages: list[str] = ["fr"]
    capacity: int = Field(default=5, ge=1, le=100)
    active: bool = True


class AdvisorUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    levels: list[str] | None = None
    countries: list[str] | None = None
    domains: list[str] | None = None
    languages: list[str] | None = None
    capacity: int | None = Field(default=None, ge=1, le=100)
    active: bool | None = None


class AdvisorAdminOut(AdvisorPublic):
    email: str
    capacity: int
    active: bool
    load: int  # accompagnements en cours


class StepIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str | None = None
    due_date: date | None = None
    application_id: int | None = None


class StepUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = None
    due_date: date | None = None
    done: bool | None = None


class StepOut(ORM):
    id: int
    position: int
    title: str
    description: str | None
    due_date: date | None
    done: bool
    done_at: datetime | None
    application_id: int | None


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    application_id: int | None = None


class MessageOut(ORM):
    id: int
    author_role: str
    author_name: str | None = None
    content: str
    application_id: int | None
    created_at: datetime
    mine: bool = False


class MeetingIn(BaseModel):
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=10, le=240)
    mode: str = "visio"
    link: str | None = Field(default=None, max_length=500)
    topic: str | None = Field(default=None, max_length=300)


class MeetingUpdate(BaseModel):
    status: str | None = None
    starts_at: datetime | None = None
    link: str | None = Field(default=None, max_length=500)
    summary: str | None = None


class MeetingOut(ORM):
    id: int
    starts_at: datetime
    duration_minutes: int
    mode: str
    link: str | None
    topic: str | None
    status: str
    proposed_by: str
    summary: str | None


class StudentSummary(BaseModel):
    """Ce que le conseiller voit du candidat (seulement s'il a donné son accord)."""

    full_name: str | None
    email: str
    nationalities: list[str] = []
    residence_country: str | None = None
    current_level: str | None = None
    target_level: str | None = None
    domain: str | None = None
    institution: str | None = None
    grade_average: float | None = None
    wished_countries: list[str] = []
    languages: dict[str, str] = {}
    language_scores: dict[str, float] = {}
    project: str | None = None
    experiences: str | None = None
    cv_text: str | None = None
    completeness: int = 0


class CoachingOut(BaseModel):
    id: int
    status: str
    goal: str
    needs: list[str]
    application_ids: list[int]
    preferred_language: str
    availability: str | None
    share_consent: bool
    offer: str = "standard"
    offer_name: str = ""
    price: int = 0
    price_label: str = ""
    payment_status: str = "a_payer"
    rating: int | None
    feedback: str | None
    created_at: datetime
    assigned_at: datetime | None
    closed_at: datetime | None
    advisor: AdvisorPublic | None
    student_name: str | None = None
    progress: int = 0  # % d'étapes faites
    next_step: StepOut | None = None
    next_meeting: MeetingOut | None = None
    unread: int = 0
    my_role: str = "candidat"  # candidat | conseiller | admin


class CoachingFileOut(BaseModel):
    id: int
    author_role: str
    category: str
    filename: str
    content_type: str
    size: int
    note: str | None = None
    created_at: datetime
    mine: bool = False


class CoachingDetailOut(CoachingOut):
    files: list[CoachingFileOut] = []
    steps: list[StepOut] = []
    messages: list[MessageOut] = []
    meetings: list[MeetingOut] = []
    student: StudentSummary | None = None
    applications: list[ApplicationOut] = []


class CloseIn(BaseModel):
    note: str | None = Field(default=None, max_length=3000)


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=3000)


class AssignIn(BaseModel):
    advisor_id: int


class AdminCoachingOut(CoachingOut):
    student_email: str
    suggestions: list[AdvisorAdminOut] = []
