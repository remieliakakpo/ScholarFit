"""Configuration de l'application, lue depuis les variables d'environnement (ou un fichier .env)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dossier backend/ : le fichier .env et la base SQLite y sont cherchés quel que soit le dossier
# depuis lequel l'API est lancée (sinon une base vide était créée ailleurs, sans les comptes de démo).
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ScholarFit"
    # production | local. Vide : production dès que DATABASE_URL n'est pas SQLite.
    app_env: str = ""
    # SQLite par défaut pour démarrer sans rien installer. En production :
    # postgresql+psycopg://user:pass@localhost:5432/bourses
    database_url: str = "sqlite:///./bourses.db"

    @field_validator("database_url")
    @classmethod
    def _sqlite_in_backend(cls, v: str) -> str:
        """« sqlite:///./bourses.db » désigne toujours backend/bourses.db."""
        prefix = "sqlite:///"
        if v.startswith(prefix) and not v.startswith(prefix + "/") and ":memory:" not in v:
            rel = v[len(prefix):]
            if not Path(rel).is_absolute():
                return prefix + (BACKEND_DIR / rel).resolve().as_posix()
        return v

    # Secret de signature des jetons de connexion. À CHANGER en production.
    secret_key: str = "dev-secret-a-changer-absolument-en-production-0123456789"
    token_expire_minutes: int = 60 * 24 * 7

    # Origines autorisées à appeler l'API (le site Next.js en local)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # IA : si aucune clé n'est fournie, la plateforme fonctionne en mode hors-ligne
    # (extraction par règles, lettres et diagnostics à partir de modèles).
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    ai_free_generations_per_day: int = 20

    # Collecte
    scraper_user_agent: str = "ScholarFitBot/0.1 (+https://example.org/bot)"
    scraper_min_delay_seconds: float = 5.0

    # Accompagnement : attribue tout de suite le conseiller le plus adapté qui a de la place.
    # À false, chaque demande attend qu'un administrateur choisisse le conseiller dans /admin.
    coaching_auto_assign: bool = True

    # Offres d'accompagnement (prix en F CFA)
    offer_standard_price: int = 15000
    offer_premium_price: int = 35000

    # CV et lettres : un dossier (CV adapté + lettre pour une bourse) est offert à chaque compte.
    # Ensuite, abonnement mensuel : SUBSCRIPTION_PRICE F CFA pour SUBSCRIPTION_DAYS jours, qui
    # permet de préparer jusqu'à SUBSCRIPTION_MONTHLY_PACKS dossiers (limite qui maîtrise le coût de l'IA).
    # Relances de génération permises dans un même dossier.
    doc_free_packs: int = 1
    subscription_price: int = 2500
    subscription_days: int = 30
    subscription_monthly_packs: int = 10
    doc_pack_regenerations: int = 3
    # Numéros qui reçoivent les paiements (Flooz = Moov Africa, Mixx by Yas)
    payment_flooz_number: str = "+228 98 64 55 43"
    payment_mixx_number: str = "+228 91 12 75 84"
    payment_beneficiary: str = "ScholarFit"

    # Collecte automatique : toutes les N heures, l'API relance les sources, la découverte par IA,
    # la vérification des liens et les expirations (0 = désactivé, utiliser alors « python -m app.cli nightly »).
    # Chaque source garde sa propre fréquence (sources.json, une fois par semaine) : ce réglage dit seulement à quel rythme on regarde.
    auto_collect_hours: float = 24
    # Stages des organisations internationales (API ReliefWeb) : nom d'application approuvé
    reliefweb_appname: str = ""
    # Découverte de nouvelles bourses par l'IA (recherche web Claude), région par région
    ai_discovery_enabled: bool = True
    ai_discovery_max_searches: int = 6  # recherches web par région et par passage (coût maîtrisé)

    # Adresse publique de l'API (notifications CinetPay). SITE_URL est plus bas, avec les e-mails.
    api_public_url: str = "http://localhost:8000"

    # Paiement en ligne : simulation (essais, aucun argent ne circule) | cinetpay | manuel (désactivé)
    payment_provider: str = "simulation"
    cinetpay_apikey: str = ""
    cinetpay_site_id: str = ""
    cinetpay_secret_key: str = ""  # vérifie la signature x-token des notifications
    cinetpay_api_url: str = "https://api-checkout.cinetpay.com/v2"

    # E-mails : console (affichés dans le terminal) | smtp | brevo | resend.
    # Vide : smtp si SMTP_HOST est renseigné, sinon console. L'expéditeur est SMTP_FROM (plus bas).
    email_backend: str = ""
    email_reply_to: str = ""
    brevo_api_key: str = ""
    resend_api_key: str = ""

    # Comptes administrateurs (e-mails séparés par des virgules)
    admin_emails: str = "admin@example.org"
    # Comptes de démonstration (admin, étudiante, conseiller) créés ou réparés à chaque démarrage
    # avec les mots de passe du README. À false en production une fois vos vrais comptes créés.
    demo_accounts: bool = True

    # Adresse publique du site, utilisée dans les liens des e-mails (confirmation, mot de passe oublié)
    site_url: str = "http://localhost:3000"
    # Envoi des e-mails. Sans SMTP_HOST, les e-mails (et leurs liens) sont écrits dans la console de l'API.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ScholarFit <no-reply@scholarfit.local>"
    smtp_ssl: bool = False  # true pour le port 465 ; sinon STARTTLS sur le port 587
    # Durée de validité des liens envoyés par e-mail
    verify_link_hours: int = 48
    reset_link_minutes: int = 60

    # Limite de requêtes par adresse IP (connexion, inscription, assistant…)
    rate_limit_enabled: bool = True
    # Suivi des erreurs (facultatif) : adresse DSN d'un projet Sentry. Vide = désactivé.
    sentry_dsn: str = ""

    @property
    def is_production(self) -> bool:
        """En ligne = base PostgreSQL (ou APP_ENV=production). SQLite = poste local ou tests."""
        return self.app_env.strip().lower() == "production" or (
            self.app_env.strip().lower() != "local" and not self.database_url.startswith("sqlite"))

    @property
    def demo_enabled(self) -> bool:
        """Comptes de démonstration : jamais en production, quoi que dise DEMO_ACCOUNTS."""
        return self.demo_accounts and not self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mail_backend(self) -> str:
        b = (self.email_backend or "").strip().lower()
        if b in ("console", "smtp", "brevo", "resend"):
            return b
        return "smtp" if self.smtp_host else "console"

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
