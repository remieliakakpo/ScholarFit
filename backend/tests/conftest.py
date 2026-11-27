import os
import sys
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent.parent / "test_bourses.db"
os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()
os.environ["ANTHROPIC_API_KEY"] = ""  # les tests tournent en mode hors-ligne
os.environ["ADMIN_EMAILS"] = "admin@example.org"
os.environ["AUTO_COLLECT_HOURS"] = "0"  # pas de collecte en arrière-plan pendant les tests
os.environ["SMTP_HOST"] = ""  # e-mails écrits dans la console
os.environ["DEMO_ACCOUNTS"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    db_file = TEST_DB
    if db_file.exists():
        db_file.unlink()
    from app.cli import seed
    from app.main import app

    seed()
    with TestClient(app) as c:
        yield c
    db_file.unlink(missing_ok=True)


def login(client, email="demo@example.org", password="demo12345"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def demo(client):
    return login(client)


@pytest.fixture()
def admin(client):
    return login(client, "admin@example.org", "admin12345")
