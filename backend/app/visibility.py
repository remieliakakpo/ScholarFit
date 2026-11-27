"""Fiches visibles du public : publiées (relues) et dont le lien officiel n'est pas cassé."""
from .models import Scholarship


def public_filter():
    return (Scholarship.review == "publie") | (Scholarship.review.is_(None))


def is_public(s: Scholarship) -> bool:
    return (s.review in (None, "publie")) and s.link_status != "casse"
