"""Export des CV et lettres en PDF et en Word (.docx).

Mise en page sobre, comme un document rédigé dans Word : A4, marges classiques, police
Carlito (métriquement identique à Calibri) pour le CV, Caladea (identique à Cambria) pour la
lettre, aucun cadre ni couleur de fond. Les polices sont libres (SIL OFL) et intégrées au PDF.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

FONT_DIR = Path(__file__).parent / "fonts"
ACCENT = "#1F3A5F"  # bleu nuit sobre pour les titres de rubrique du CV
_fonts_ready = False


def _register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for family, files in {
        "Carlito": {"normal": "Carlito-Regular.ttf", "bold": "Carlito-Bold.ttf", "italic": "Carlito-Italic.ttf", "bolditalic": "Carlito-Bold.ttf"},
        "Caladea": {"normal": "Caladea-Regular.ttf", "bold": "Caladea-Bold.ttf", "italic": "Caladea-Italic.ttf", "bolditalic": "Caladea-BoldItalic.ttf"},
    }.items():
        for style, fname in files.items():
            name = family if style == "normal" else f"{family}-{style}"
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / fname)))
        addMapping(family, 0, 0, family)
        addMapping(family, 1, 0, f"{family}-bold")
        addMapping(family, 0, 1, f"{family}-italic")
        addMapping(family, 1, 1, f"{family}-bolditalic")
    _fonts_ready = True


def safe_filename(*parts: str) -> str:
    import unicodedata

    raw = "-".join(p for p in parts if p)
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    raw = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-")
    return (raw or "document")[:80]


def _e(text: str) -> str:
    return escape(text or "")


# ====================================================================== CV : PDF
def cv_pdf(cv: dict) -> bytes:
    _register_fonts()
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    accent = HexColor(ACCENT)
    grey = HexColor("#555555")
    centered = cv.get("layout") != "dated"  # modèle ATS : en-tête centré
    base = ParagraphStyle("base", fontName="Carlito", fontSize=10.2, leading=12.9, textColor=HexColor("#1a1a1a"))
    name_st = ParagraphStyle("name", parent=base, fontName="Carlito-bold", fontSize=21, leading=25, alignment=TA_CENTER if centered else TA_LEFT)
    head_st = ParagraphStyle("headline", parent=base, fontName="Carlito-bold", fontSize=11, leading=14.5, textColor=accent, alignment=TA_CENTER if centered else TA_LEFT)
    contact_st = ParagraphStyle("contact", parent=base, fontSize=9.8, textColor=grey, alignment=TA_CENTER if centered else TA_LEFT)
    sec_st = ParagraphStyle("section", parent=base, fontName="Carlito-bold", fontSize=11.5, leading=14, textColor=accent, spaceBefore=9, spaceAfter=1)
    title_st = ParagraphStyle("etitle", parent=base, fontName="Carlito-bold")
    org_st = ParagraphStyle("eorg", parent=base, fontName="Carlito-italic", textColor=grey)
    date_st = ParagraphStyle("edate", parent=base, textColor=grey, alignment=2)
    date_left = ParagraphStyle("edateleft", parent=base, textColor=grey)
    bullet_st = ParagraphStyle("bullet", parent=base, leftIndent=11, bulletIndent=2, spaceBefore=0.5)
    item_st = ParagraphStyle("item", parent=base, spaceBefore=0.5)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=13 * mm, bottomMargin=13 * mm,
                            title=f"CV {cv.get('header', {}).get('name', '')}".strip(), author=cv.get("header", {}).get("name", ""))
    width = A4[0] - 34 * mm
    h = cv.get("header", {})
    story = [Paragraph(_e(h.get("name", "").upper() if centered else h.get("name", "")), name_st)]
    if h.get("headline"):
        story.append(Paragraph(_e(h["headline"].upper()), head_st))
    contact = [x for x in [h.get("location"), h.get("phone"), h.get("email"), h.get("links")] if x]
    if contact:
        story.append(Spacer(1, 2))
        story.append(Paragraph("  |  ".join(_e(x) for x in contact), contact_st))
    if h.get("objective"):
        story.append(Paragraph(_e(h["objective"]), contact_st))
    personal = []
    lang = cv.get("language", "fr")
    if h.get("birth_date"):
        personal.append(f"Date of birth {h['birth_date']}" if lang == "en" else f"Date de naissance {h['birth_date']}")
    if h.get("nationality"):
        personal.append((f"Nationality {h['nationality']}" if lang == "en" else f"Nationalité {h['nationality']}"))
    if personal:
        story.append(Paragraph("  |  ".join(_e(x) for x in personal), contact_st))
    story.append(Spacer(1, 5))

    pending: list = []  # titre de rubrique gardé avec son premier contenu (jamais seul en bas de page)

    def section(title: str):
        pending[:] = [Paragraph(_e(title.upper()), sec_st), HRFlowable(width="100%", thickness=0.6, color=accent, spaceBefore=1, spaceAfter=4)]

    def add(*flow):
        if pending:
            story.append(KeepTogether(pending + list(flow)))
            pending.clear()
        else:
            story.append(KeepTogether(list(flow)) if len(flow) > 1 else flow[0])

    if cv.get("summary"):
        section(cv.get("summary_title") or "Profil")
        add(Paragraph(_e(cv["summary"]), base))

    dated = cv.get("layout") == "dated"
    for sec in cv.get("sections", []):
        section(sec.get("title", ""))
        if sec.get("kind") == "list":
            for it in sec.get("items", []):
                cat, sep, rest = it.partition(" : ") if " : " in it else it.partition(": ")
                if sep and sec.get("key") == "skills" and len(cat.split()) <= 5:
                    add(Paragraph(f"<b>{_e(cat)}{_e(sep.rstrip())}</b> {_e(rest)}", item_st))
                else:
                    add(Paragraph(_e(it), item_st))
            continue
        for e in sec.get("entries", []):
            block = []
            title = _e(e.get("title", ""))
            if not dated:
                extra = " | ".join(_e(x) for x in [e.get("organization"), e.get("location")] if x)
                title = f"<b>{title}</b>" + (f" | {extra}" if extra and title else extra)
            org = ", ".join(x for x in [e.get("organization"), e.get("location")] if x)
            bullets = [Paragraph(_e(b), bullet_st, bulletText="•") for b in e.get("bullets", [])]
            if dated:
                right = [Paragraph(title, title_st)]
                if org:
                    right.append(Paragraph(_e(org), org_st))
                right += bullets
                t = Table([[Paragraph(_e(e.get("dates", "")), date_left), right]], colWidths=[36 * mm, width - 36 * mm], hAlign="LEFT")
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 6),
                                       ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
                block.append(t)
            else:
                if title or e.get("dates"):
                    t = Table([[Paragraph(title, base), Paragraph(_e(e.get("dates", "")), date_st)]], colWidths=[width - 42 * mm, 42 * mm], hAlign="LEFT")
                    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                    block.append(t)
                block += bullets
                block.append(Spacer(1, 4))
            add(*block)
    if cv.get("signature"):
        story.append(Spacer(1, 18))
        story.append(Paragraph(_e(cv["signature"]), base))
        story.append(Paragraph(_e(h.get("name", "")), base))
    doc.build(story)
    return buf.getvalue()


# ====================================================================== lettre : PDF
def letter_pdf(letter: dict) -> bytes:
    _register_fonts()
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    ink = HexColor("#111111")
    base = ParagraphStyle("base", fontName="Caladea", fontSize=11.5, leading=16, textColor=ink)
    body = ParagraphStyle("body", parent=base, alignment=TA_JUSTIFY, spaceAfter=9)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    recip = ParagraphStyle("recip", parent=base, leftIndent=95 * mm, alignment=TA_LEFT)
    subject = ParagraphStyle("subject", parent=base, fontName="Caladea-bold")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
                            title=letter.get("subject", "Lettre de motivation"), author=letter.get("signature", ""))
    style = letter.get("style", "fr")
    story = []
    sender = letter.get("sender", [])
    if sender:
        story.append(Paragraph("<br/>".join(_e(x) for x in sender), base))
    story.append(Spacer(1, 14))
    if style == "fr":
        story.append(Paragraph("<br/>".join(_e(x) for x in letter.get("recipient", [])), recip))
        story.append(Spacer(1, 14))
        story.append(Paragraph(_e(letter.get("place_date", "")), right))
    else:
        story.append(Paragraph(_e(letter.get("place_date", "")), base))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<br/>".join(_e(x) for x in letter.get("recipient", [])), base))
    story.append(Spacer(1, 16))
    if letter.get("subject"):
        story.append(Paragraph(_e(letter["subject"]), subject))
        story.append(Spacer(1, 12))
    story.append(Paragraph(_e(letter.get("salutation", "")), base))
    story.append(Spacer(1, 9))
    for para in letter.get("paragraphs", []):
        story.append(Paragraph(_e(para), body))
    if style == "fr":
        story.append(Paragraph(_e(letter.get("closing", "")), body))
        story.append(Spacer(1, 16))
        story.append(Paragraph(_e(letter.get("signature", "")), ParagraphStyle("sig", parent=base, leftIndent=95 * mm)))
    else:
        story.append(Spacer(1, 4))
        story.append(Paragraph(_e(letter.get("closing", "")), base))
        story.append(Spacer(1, 26))
        story.append(Paragraph(_e(letter.get("signature", "")), base))
    doc.build(story)
    return buf.getvalue()


# ====================================================================== Word
def _docx_base(font: str, size: float, margins_mm: tuple[float, float, float, float]):
    import docx
    from docx.shared import Mm, Pt

    d = docx.Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.top_margin, sec.right_margin, sec.bottom_margin, sec.left_margin = (Mm(m) for m in margins_mm)
    st = d.styles["Normal"]
    st.font.name = font
    st.font.size = Pt(size)
    rpr = st.element.get_or_add_rPr()
    rfonts = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    if rfonts is not None:
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            rfonts.set(f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attr}", font)
    st.paragraph_format.space_after = Pt(0)
    st.paragraph_format.line_spacing = 1.1
    return d


def _para(d, text: str = "", bold=False, italic=False, size=None, color=None, align=None, space_after=0, space_before=0, indent_mm=0):
    from docx.shared import Mm, Pt, RGBColor

    p = d.add_paragraph()
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
    pf = p.paragraph_format
    pf.space_after, pf.space_before = Pt(space_after), Pt(space_before)
    if indent_mm:
        pf.left_indent = Mm(indent_mm)
    if align is not None:
        p.alignment = align
    return p


def _bottom_border(p, color: str = ACCENT):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", color.lstrip("#"))):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    ppr.append(bdr)


def cv_docx(cv: dict) -> bytes:
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Mm, Pt

    d = _docx_base("Calibri", 10.5, (16, 18, 16, 18))
    centered = cv.get("layout") != "dated"  # modèle ATS : en-tête centré
    align = WD_ALIGN_PARAGRAPH.CENTER if centered else None
    h = cv.get("header", {})
    _para(d, h.get("name", "").upper() if centered else h.get("name", ""), bold=True, size=21, align=align)
    if h.get("headline"):
        _para(d, h["headline"].upper(), bold=True, size=11, color=ACCENT, align=align)
    contact = [x for x in [h.get("location"), h.get("phone"), h.get("email"), h.get("links")] if x]
    if contact:
        _para(d, "  |  ".join(contact), size=9.8, color="#555555", align=align, space_before=2)
    if h.get("objective"):
        _para(d, h["objective"], size=9.8, color="#555555", align=align)
    lang = cv.get("language", "fr")
    personal = []
    if h.get("birth_date"):
        personal.append(f"Date of birth {h['birth_date']}" if lang == "en" else f"Date de naissance {h['birth_date']}")
    if h.get("nationality"):
        personal.append(f"Nationality {h['nationality']}" if lang == "en" else f"Nationalité {h['nationality']}")
    if personal:
        _para(d, "  |  ".join(personal), size=9.8, color="#555555", align=align)

    def section(title: str):
        p = _para(d, title.upper(), bold=True, size=11.5, color=ACCENT, space_before=10, space_after=4)
        _bottom_border(p)

    if cv.get("summary"):
        section(cv.get("summary_title") or "Profil")
        _para(d, cv["summary"])
    dated = cv.get("layout") == "dated"
    for sec in cv.get("sections", []):
        section(sec.get("title", ""))
        if sec.get("kind") == "list":
            for it in sec.get("items", []):
                cat, sep, rest = it.partition(" : ") if " : " in it else it.partition(": ")
                if sep and sec.get("key") == "skills" and len(cat.split()) <= 5:
                    p = d.add_paragraph()
                    p.paragraph_format.space_after = Pt(1)
                    p.add_run(cat + sep.rstrip()).bold = True
                    p.add_run(" " + rest)
                else:
                    _para(d, it, space_after=1)
            continue
        for e in sec.get("entries", []):
            org = ", ".join(x for x in [e.get("organization"), e.get("location")] if x)
            if dated:
                t = d.add_table(rows=1, cols=2)
                t.alignment = WD_TABLE_ALIGNMENT.LEFT
                t.autofit = False
                c0, c1 = t.rows[0].cells
                c0.width, c1.width = Mm(34), Mm(140)
                c0.paragraphs[0].add_run(e.get("dates", ""))
                c1.paragraphs[0].add_run(e.get("title", "")).bold = True
                if org:
                    r = c1.add_paragraph().add_run(org)
                    r.italic = True
                for b in e.get("bullets", []):
                    bp = c1.add_paragraph(b, style="List Bullet")
                    bp.paragraph_format.space_after = Pt(0)
                _para(d, "", space_after=2)
            else:
                if e.get("title") or e.get("dates") or org:
                    p = d.add_paragraph()
                    p.paragraph_format.tab_stops.add_tab_stop(Mm(174), alignment=2)  # 2 = droite
                    p.add_run(e.get("title", "")).bold = True
                    extra = " | ".join(x for x in [e.get("organization"), e.get("location")] if x)
                    if extra:
                        p.add_run((" | " if e.get("title") else "") + extra)
                    if e.get("dates"):
                        p.add_run("\t" + e["dates"])
                for b in e.get("bullets", []):
                    bp = d.add_paragraph(b, style="List Bullet")
                    bp.paragraph_format.space_after = Pt(0)
                _para(d, "", space_after=2)
    if cv.get("signature"):
        _para(d, "", space_after=14)
        _para(d, cv["signature"])
        _para(d, h.get("name", ""))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def letter_docx(letter: dict) -> bytes:
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    d = _docx_base("Cambria", 11.5, (22, 25, 20, 25))
    style = letter.get("style", "fr")
    for line in letter.get("sender", []):
        _para(d, line)
    _para(d, "", space_after=12)
    if style == "fr":
        for line in letter.get("recipient", []):
            _para(d, line, indent_mm=95)
        _para(d, "", space_after=12)
        _para(d, letter.get("place_date", ""), align=WD_ALIGN_PARAGRAPH.RIGHT)
    else:
        _para(d, letter.get("place_date", ""))
        _para(d, "", space_after=10)
        for line in letter.get("recipient", []):
            _para(d, line)
    _para(d, "", space_after=14)
    if letter.get("subject"):
        _para(d, letter["subject"], bold=True, space_after=12)
    _para(d, letter.get("salutation", ""), space_after=9)
    for para in letter.get("paragraphs", []):
        _para(d, para, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=9)
    if style == "fr":
        _para(d, letter.get("closing", ""), align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=24)
        _para(d, letter.get("signature", ""), indent_mm=95)
    else:
        _para(d, letter.get("closing", ""), space_before=4, space_after=30)
        _para(d, letter.get("signature", ""))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
