"""Preuves de paiement (capture d'écran ou photo du reçu Mobile Money) jointes à un paiement d'abonnement.

Sans prestataire de paiement branché, l'administrateur valide chaque paiement à la main : la preuve
lui évite de chercher la transaction. Sécurité :
- seules les images JPEG, PNG et WebP sont acceptées, vérifiées par leur contenu (pas par leur nom) ;
- l'image est réenregistrée en JPEG : on retire ainsi ses métadonnées (position GPS de la photo,
  modèle du téléphone) et tout contenu caché, et on la limite à 2 000 pixels de côté ;
- le fichier est rangé hors du site public (UPLOAD_DIR), sous un nom tiré au hasard, et n'est servi
  qu'à son propriétaire et aux administrateurs ; il est effacé avec le compte.
"""
from __future__ import annotations

import io
import secrets
from pathlib import Path

from fastapi import HTTPException

from .config import get_settings
from .i18n import t

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 2000
ACCEPTED = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO : JPEG de certains téléphones


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / root
    return root


def save_proof(data: bytes) -> str:
    """Valide et réenregistre l'image ; renvoie son chemin relatif dans UPLOAD_DIR."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not data:
        raise HTTPException(422, t("Fichier vide", "Empty file"))
    if len(data) > MAX_BYTES:
        raise HTTPException(413, t("Image trop lourde (5 Mo maximum)", "Image too large (5 MB maximum)"))
    Image.MAX_IMAGE_PIXELS = 40_000_000  # garde-fou contre une image « bombe »
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ACCEPTED:
            raise UnidentifiedImageError(fmt)
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)  # garde le bon sens de la photo, puis on oublie l'EXIF
            img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            img.save(out, "JPEG", quality=85, optimize=True)  # sans métadonnées
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise HTTPException(422, t("Envoyez une capture d'écran ou une photo du reçu (JPEG, PNG ou WebP).",
                                   "Send a screenshot or a photo of the receipt (JPEG, PNG or WebP).")) from e
    rel = f"preuves/{secrets.token_hex(16)}.jpg"
    path = upload_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.getvalue())
    return rel


def proof_path(rel: str) -> Path:
    path = (upload_root() / rel).resolve()
    if upload_root().resolve() not in path.parents:  # jamais en dehors du dossier des preuves
        raise HTTPException(404, t("Preuve introuvable", "Proof not found"))
    return path


def delete_proof(rel: str | None) -> None:
    if not rel:
        return
    try:
        proof_path(rel).unlink(missing_ok=True)
    except HTTPException:
        pass
