"""Lecture des CV importés et découpage en sections.

Les fonctions métier sont dans des modules dédiés :
- ``cv.py`` : diagnostic du CV et version adaptée à une bourse ;
- ``letter.py`` : lettre de motivation ;
- ``fit.py`` : compatibilité profil + CV avec une bourse, avant de postuler.

Règle commune : la plateforme met en valeur ce que l'étudiant a réellement fait. Aucune
expérience, note, date ou distinction n'est ajoutée.
"""
from __future__ import annotations

import io
import re

# ------------------------------------------------------------------ import
def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if name.endswith(".docx"):
        import docx

        d = docx.Document(io.BytesIO(data))
        lines = [p.text for p in d.paragraphs]
        for table in d.tables:  # beaucoup de CV Word sont mis en page dans des tableaux
            for row in table.rows:
                seen = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    lines.extend(p.text for p in cell.paragraphs)
        return "\n".join(lines).strip()
    return data.decode("utf-8", errors="ignore").strip()


# ------------------------------------------------------------------ sections
SECTION_PATTERNS = {
    "profil": r"^(profil|r[ée]sum[ée]|summary|objecti(f|ve)|about me|[àa] propos|personal statement)\b",
    "formation": r"formation|[ée]ducation|parcours (scolaire|acad[ée]mique|universitaire)|dipl[ôo]mes?|education|cursus",
    "recherche": r"^(recherche|research|travaux de recherche|exp[ée]rience de recherche)",
    "publications": r"^(publications?|communications?|conf[ée]rences?)\b",
    "experiences": r"exp[ée]riences?|stages?|emplois?|work experience|professional|internships?|parcours professionnel",
    "competences": r"comp[ée]tences|skills|savoir-faire|outils|informatique|logiciels",
    "langues": r"langues|languages",
    "engagement": r"engagements?|associati|b[ée]n[ée]volat|vie associative|volunteer|activit[ée]s|leadership",
    "projets": r"projets?|projects|r[ée]alisations",
    "centres_interet": r"centres? d.int[ée]r[êe]ts?|loisirs|hobbies|interests|passe-temps",
    "references": r"^(r[ée]f[ée]rences?|referees?)\b",
    "distinctions": r"^(prix|distinctions?|awards?|honou?rs|certifications?)\b",
}
SECTION_KEYS = {
    "profil": "summary", "formation": "education", "recherche": "research", "publications": "publications",
    "experiences": "experience", "competences": "skills", "langues": "languages", "engagement": "engagement",
    "projets": "projects", "centres_interet": "interests", "references": "references", "distinctions": "awards",
}


def _is_heading(line: str) -> str | None:
    clean = line.strip().strip(":").strip()
    if len(clean) >= 45 or len(clean.split()) > 5:
        return None
    for key, pat in SECTION_PATTERNS.items():
        if re.search(pat, clean, re.I):
            # « Stage chez X » n'est pas un titre : un titre n'a pas de date ni de préposition finale
            if re.search(r"\b(19|20)\d{2}\b", clean):
                return None
            return key
    return None


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"entete": []}
    current = "entete"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        found = _is_heading(line)
        if found:
            current = found
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in sections.items() if v}


# Compatibilité : anciens noms utilisés ailleurs dans le code et les tests
def review_cv(text: str, target_format: str, scholarship, use_ai: bool) -> dict:  # pragma: no cover - alias
    from .cv import diagnose

    return diagnose(text, None, scholarship, use_ai=use_ai)
