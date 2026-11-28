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

    # Supervision : suivi des erreurs par Sentry (ou compatible : GlitchTip…) si une adresse est donnée
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    # Coût de l'IA (dollars US). Tarifs Claude Opus 5.5 par million de jetons ; à adapter si
    # CLAUDE_MODEL change. Le prix de la recherche web est une estimation : vérifier la grille
    # tarifaire d'Anthropic.
    ai_price_input_per_mtok: float = 4.0
    ai_price_output_per_mtok: float = 20.0
    ai_price_cache_read_per_mtok: float = 0.20
    ai_price_cache_write_per_mtok: float = 5.0
    ai_price_per_web_search: float = 0.01
    # Premier passage de l'extraction (modèle économique) et relecture ciblée des fiches douteuses.
    # Tarifs Claude Haiku 5.5 par million de jetons (jusqu'à 100 000 jetons par demande) ; la lecture
    # du cache est une estimation, à vérifier dans la grille d'Anthropic.
    extract_model: str = "claude-haiku-5-5"
    review_model: str = ""  # vide = CLAUDE_MODEL
    ai_price_small_input_per_mtok: float = 0.10
    ai_price_small_output_per_mtok: float = 0.50
    ai_price_small_cache_read_per_mtok: float = 0.01
    # Premier passage avec un modèle installé sur une machine à vous (Ollama) au lieu de Claude :
    # EXTRACT_PROVIDER=ollama. La relecture ciblée reste faite par Claude si une clé est configurée.
    extract_provider: str = "claude"  # claude | ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    # Fichiers envoyés par les utilisateurs (preuves de paiement), hors du site public. Relatif au
    # dossier backend/ ; en Docker, monter un volume dessus pour ne pas les perdre.
    upload_dir: str = "uploads"

    # Collecte : travaux d'IA sans personne qui attend (extraction, mise en forme, traduction)
    # envoyés par lots (Batch API, moitié prix, réponse en moins de 24 h). false = appels immédiats.
    ai_use_batch: bool = True
    # Réutiliser une réponse de l'IA pour une demande identique (diagnostic de CV, conseils…), en jours
    ai_cache_days: int = 30
    # Plafond de dépense par jour : au-delà, l'IA est coupée jusqu'au lendemain (0 = pas de plafond)
    ai_daily_budget_usd: float = 0.0

    # E-mails (vérification d'adresse, mot de passe oublié). Sans SMTP_HOST, les e-mails sont
    # écrits dans le journal de l'API (pratique en développement, à configurer en production).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ScholarFit <no-reply@example.org>"
    smtp_starttls: bool = True

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
    def review_model_name(self) -> str:
        return self.review_model or self.claude_model

    @property
    def is_dev(self) -> bool:
        return self.app_env.strip().lower() in {"dev", "development", "developpement", "test"}

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
