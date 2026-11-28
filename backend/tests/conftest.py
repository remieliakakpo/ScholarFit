import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "dev"  # comptes de démo, cookie sans Secure (le client de test parle en HTTP)
TEST_DB = Path(__file__).resolve().parent.parent / "test_bourses.db"
os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()
os.environ["ANTHROPIC_API_KEY"] = ""  # les tests tournent en mode hors-ligne
os.environ["ADMIN_EMAILS"] = "admin@example.org"
os.environ["AUTO_COLLECT_HOURS"] = "0"  # pas de collecte en arrière-plan pendant les tests
os.environ["SMTP_HOST"] = ""  # e-mails écrits dans la console
os.environ["EMAIL_BACKEND"] = "console"
os.environ["DEMO_ACCOUNTS"] = "true"
os.environ["PAYMENT_PROVIDER"] = "simulation"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    db_file = TEST_DB
    from app.db import engine as _engine

    _engine.dispose()  # des tests unitaires ont pu ouvrir la base (suivi des coûts IA) : on la libère
    if db_file.exists():
        db_file.unlink()
    from app.cli import seed
    from app.main import app

    seed()
    # Le site ajoute cet en-tête à chaque appel (protection CSRF, voir app/main.py)
    with TestClient(app, headers={"X-Requested-With": "ScholarFit"}) as c:
        yield c
    from app.db import engine

    engine.dispose()  # sous Windows, le fichier reste verrouillé tant qu'une connexion est ouverte
    db_file.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _fresh_state(request):
    """Chaque test part sans cookie gardé par le client et sans compteur de tentatives."""
    from app import ratelimit

    ratelimit.reset()
    if "client" in request.fixturenames:
        request.getfixturevalue("client").cookies.clear()
    yield


def session_headers(client, response) -> dict:
    """En-tête Cookie de la session ouverte par `response` (connexion ou inscription). Le cookie
    n'est pas gardé dans le client : chaque appel dit explicitement pour qui il est fait."""
    from app.config import get_settings

    name = get_settings().session_cookie_name
    token = response.cookies.get(name)
    assert token, response.text
    client.cookies.clear()
    return {"Cookie": f"{name}={token}"}


def login(client, email="demo@example.org", password="demo12345"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return session_headers(client, r)


def register(client, email, password="motdepasse1", verify=True):
    """Inscription ; par défaut l'adresse est aussi confirmée (comme après le clic sur le lien reçu)."""
    r = client.post("/api/auth/register", json={"email": email, "password": password, "accept_terms": True})
    assert r.status_code == 201, r.text
    h = session_headers(client, r)
    if verify:
        from app.db import SessionLocal
        from app.models import User
        from app.security import VERIFY_EMAIL, create_link_token

        db = SessionLocal()
        try:
            user = db.get(User, r.json()["id"])
            token = create_link_token(user, VERIFY_EMAIL, 60)
        finally:
            db.close()
        assert client.post("/api/auth/verifier-email", json={"token": token}).status_code == 200
    return h


@pytest.fixture()
def demo(client):
    return login(client)


@pytest.fixture()
def admin(client):
    return login(client, "admin@example.org", "admin12345")
