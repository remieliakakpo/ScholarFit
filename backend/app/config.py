"""Configuration de l'application, lue depuis les variables d'environnement (ou un fichier .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_SECRET = "dev-secret-a-changer-absolument-en-production-0123456789"
# Valeurs d'exemple publiées dans ce dépôt : refusées en production.
KNOWN_SECRETS = {
    DEV_SECRET,
    "change-moi-avec-une-longue-chaine-aleatoire",
    "change-moi-en-production-avec-une-longue-chaine",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ScholarFit"
    # « dev » sur un poste de développement (comptes de démo, documentation /docs, cookie sans Secure).
    # Toute autre valeur est traitée comme la production : l'API refuse alors de démarrer avec un
    # secret faible ou connu, et aucun compte de démo n'est créé.
    app_env: str = "production"
    # Adresse publique du site, pour les liens envoyés par e-mail (vérification, mot de passe oublié)
    frontend_url: str = "http://localhost:3000"
    # SQLite par défaut pour démarrer sans rien installer. En production :
    # postgresql+psycopg://user:pass@localhost:5432/bourses
    database_url: str = "sqlite:///./bourses.db"

    # Secret de signature des sessions et des liens envoyés par e-mail. Obligatoire en production :
    # au moins 32 caractères aléatoires (python -c "import secrets; print(secrets.token_urlsafe(48))").
    secret_key: str = DEV_SECRET
    # Session dans un cookie httpOnly : valable 24 h, renouvelée tant que la personne est active,
    # sans dépasser session_max_days depuis la connexion (il faut alors se reconnecter).
    session_cookie_name: str = "sf_session"
    token_expire_minutes: int = 60 * 24
    session_max_days: int = 30
    # Adresses des relais (le serveur Next.js) dont on accepte l'en-tête X-Forwarded-For pour
    # connaître l'adresse réelle du visiteur (limitation des tentatives). « * » = tous : à réserver
    # au cas où l'API n'est joignable que par le site (réseau Docker interne).
    trusted_proxies: str = "127.0.0.1,::1"
    # Taille maximale d'une requête (Mo). Le dépôt du CV a sa propre limite (5 Mo + enveloppe).
    max_request_mb: float = 1.0
    # Collecte : autoriser les adresses internes (localhost, réseau privé). Jamais en production.
    fetch_allow_private: bool = False

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

    # CV et lettres : un dossier (CV adapté + lettre pour une bourse) est offert, les suivants
    # sont payants. Relances de génération permises dans un même dossier.
    doc_free_packs: int = 1
    doc_pack_price: int = 2500
    doc_pack_regenerations: int = 3
    # Numéros qui reçoivent les paiements (Flooz = Moov Africa, Mixx by Yas)
    payment_flooz_number: str = "+228 98 64 55 43"
    payment_mixx_number: str = "+228 91 12 75 84"
    payment_beneficiary: str = "ScholarFit"

    # Collecte automatique : toutes les N heures, l'API relance les sources, la découverte par IA,
    # la vérification des liens et les expirations (0 = désactivé, utiliser alors « python -m app.cli nightly »).
    # Chaque source garde sa propre fréquence (sources.json) : ce réglage dit seulement à quel rythme on regarde.
    auto_collect_hours: float = 6
    # Stages des organisations internationales (API ReliefWeb) : nom d'application approuvé
    reliefweb_appname: str = ""
    # Découverte de nouvelles bourses par l'IA (recherche web Claude), région par région
    ai_discovery_enabled: bool = True
    ai_discovery_max_searches: int = 6  # recherches web par région et par passage (coût maîtrisé)

    # Comptes administrateurs (e-mails séparés par des virgules)
    admin_emails: str = "admin@example.org"

    @property
    def is_dev(self) -> bool:
        return self.app_env.strip().lower() in {"dev", "development", "developpement", "test"}

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]

    def check_production(self) -> None:
        """Refuse de démarrer hors développement avec une configuration dangereuse."""
        if self.is_dev:
            return
        problems = []
        if len(self.secret_key) < 32 or self.secret_key in KNOWN_SECRETS:
            problems.append("SECRET_KEY absente, trop courte (32 caractères minimum) ou reprise d'un exemple du dépôt")
        if problems:
            raise RuntimeError(
                "Configuration refusée (APP_ENV=" + self.app_env + ") : " + " ; ".join(problems)
                + ". Pour un poste de développement, mettez APP_ENV=dev dans backend/.env."
            )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
