"""Preuve de paiement jointe à une déclaration d'abonnement : image vérifiée, nettoyée et privée."""
import io

import pytest
from PIL import Image

from tests.conftest import register


@pytest.fixture()
def uploads(tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def _photo(fmt="PNG", size=(3000, 1500)) -> bytes:
    img = Image.new("RGB", size, (200, 30, 30))
    out = io.BytesIO()
    if fmt == "JPEG":
        exif = Image.Exif()
        exif[0x010F] = "Telephone"  # fabricant : doit disparaître
        img.save(out, "JPEG", exif=exif)
    else:
        img.save(out, fmt)
    return out.getvalue()


def _order(client, email):
    h = register(client, email)
    o = client.post("/api/credits/orders", headers=h, json={"method": "flooz", "reference": "TX-PREUVE"}).json()
    return h, o


def test_proof_is_cleaned_private_and_visible_to_admin(client, admin, uploads):
    h, o = _order(client, "preuve@example.org")
    assert o["has_proof"] is False
    r = client.post(f"/api/credits/orders/{o['id']}/preuve", headers=h,
                    files={"file": ("recu.jpg", _photo("JPEG"), "image/jpeg")})
    assert r.status_code == 200, r.text
    assert r.json()["has_proof"] is True
    files = list((uploads / "preuves").iterdir())
    assert len(files) == 1
    with Image.open(files[0]) as img:
        assert img.format == "JPEG" and max(img.size) <= 2000
        assert not img.getexif()  # métadonnées retirées
    # Visible par son propriétaire et par l'administrateur, pas par un autre compte
    r = client.get(f"/api/credits/orders/{o['id']}/preuve", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "no-store" in r.headers["cache-control"]
    assert client.get(f"/api/credits/orders/{o['id']}/preuve", headers=admin).status_code == 200
    other = register(client, "autre-payeur@example.org")
    assert client.get(f"/api/credits/orders/{o['id']}/preuve", headers=other).status_code == 404
    assert client.post(f"/api/credits/orders/{o['id']}/preuve", headers=other,
                       files={"file": ("x.png", _photo(), "image/png")}).status_code == 404
    rows = client.get("/api/admin/credit-orders", headers=admin).json()
    assert next(x for x in rows if x["id"] == o["id"])["has_proof"] is True
    # Une nouvelle preuve remplace l'ancienne (un seul fichier gardé)
    assert client.post(f"/api/credits/orders/{o['id']}/preuve", headers=h,
                       files={"file": ("r.png", _photo(), "image/png")}).status_code == 200
    assert len(list((uploads / "preuves").iterdir())) == 1
    # Paiement traité : plus de changement de preuve
    assert client.patch(f"/api/admin/credit-orders/{o['id']}", headers=admin, json={"status": "paye"}).status_code == 200
    assert client.post(f"/api/credits/orders/{o['id']}/preuve", headers=h,
                       files={"file": ("r.png", _photo(), "image/png")}).status_code == 409
    # Suppression du compte : la capture part avec lui
    assert client.delete("/api/auth/me", headers=h).status_code == 204
    assert list((uploads / "preuves").iterdir()) == []


def test_proof_rejects_non_images(client, uploads):
    h, o = _order(client, "pasimage@example.org")
    for name, data, mime in [("recu.png", b"<script>alert(1)</script>", "image/png"),
                             ("recu.pdf", b"%PDF-1.4 faux", "application/pdf"),
                             ("vide.png", b"", "image/png")]:
        r = client.post(f"/api/credits/orders/{o['id']}/preuve", headers=h, files={"file": (name, data, mime)})
        assert r.status_code == 422, (name, r.text)
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    r = client.post(f"/api/credits/orders/{o['id']}/preuve", headers=h, files={"file": ("a.gif", gif.getvalue(), "image/gif")})
    assert r.status_code == 422
    assert not (uploads / "preuves").exists() or list((uploads / "preuves").iterdir()) == []
