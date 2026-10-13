"""Formula renderer: docx/xlsx/pptx uchun yagona notatsiya dvigateli.

Kirish notatsiyasi (prompt shartnomasi):
    daraja:  x^2, 10^-3, e^{i*pi}      indeks: x_1, a_{max} (faqat raqam/{...} — test_case buzilmaydi)
    ildiz:   sqrt(x), sqrt(a+b)         kasr:  (a+b)/c  (chiziqli ko'rinishda)
    yunon:   pi, alpha, beta ...         strelka/taqqos: ->, <=, >=, !=, +-

Yagona `parse_rich()` uchala formatga segment beradi:
    docx  -> Cambria Math + superscript/subscript runlar (tahrirlanadigan)
    xlsx  -> CellRichText (vertAlign superscript/subscript)
    pptx  -> baseline siljishli runlar (+30000/-25000)
Kod (backtick) har uchalasida Consolas/monospace.
"""
from __future__ import annotations

import re
from typing import List, Tuple

MATH_FONT = "Cambria Math"
BODY_FONT = "Calibri"
MONO_FONT = "Consolas"

UNICODE_MAP: List[Tuple[str, str]] = [
    ("<=>", "⇔"),
    ("->", "→"),
    ("<-", "←"),
    ("<=", "≤"),
    (">=", "≥"),
    ("!=", "≠"),
    ("+-", "±"),
    ("~=", "≈"),
    ("infinity", "∞"),
    ("cbrt", "∛"),
    ("sqrt", "√"),
    ("alpha", "α"),
    ("beta", "β"),
    ("gamma", "γ"),
    ("delta", "δ"),
    ("epsilon", "ε"),
    ("theta", "θ"),
    ("lambda", "λ"),
    ("mu", "μ"),
    ("pi", "π"),
    ("sigma", "σ"),
    ("omega", "ω"),
    ("Omega", "Ω"),
    ("Delta", "Δ"),
    ("Sigma", "Σ"),
]

_MUL_RE = re.compile(
    r"(?<=[\d\)\]\}a-zA-Zα-ωΑ-Ω])\s*\*\s*(?=[\d\(\[\{a-zA-Zα-ωΑ-Ω])"
)
_CODE_RE = re.compile(r"`([^`]+?)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_SUP_RE = re.compile(r"\^(\{([^{}]+)\}|([+\-]?(?:\d+|[a-zA-Zα-ωΑ-Ω])))")
_SUB_RE = re.compile(r"_(\{([^{}]+)\}|(\d+))")
_VAR_RE = re.compile(r"(?<![\w])([a-zA-Zα-ωΑ-Ω])(?![\w])")


def to_unicode_math(text: str) -> str:
    """Nomlarni Unicode matematik belgilarga almashtiradi (so'z ichini buzmaydi)."""
    out = text
    for latin, uni in UNICODE_MAP:
        if latin.isalpha():
            out = re.sub(rf"(?<![a-zA-Z]){re.escape(latin)}(?![a-zA-Z])", uni, out)
        else:
            out = out.replace(latin, uni)
    out = _MUL_RE.sub(" × ", out)
    return out


def _set_font(run, name: str, size_pt: int, bold=False, italic=False,
              superscript=False, subscript=False) -> None:
    run.font.name = name
    from docx.shared import Pt

    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.superscript = superscript
    run.font.subscript = subscript


def _add_runs(paragraph, segments: List[Tuple[str, dict]], size_pt: int) -> None:
    for text, style in segments:
        if not text:
            continue
        run = paragraph.add_run(text)
        _set_font(run, style.get("font", BODY_FONT), size_pt,
                  bold=style.get("bold", False),
                  italic=style.get("italic", False),
                  superscript=style.get("sup", False),
                  subscript=style.get("sub", False))


def _formula_segments(text: str) -> List[Tuple[str, dict]]:
    """Oddiy matn bo'lagini formula segmentlariga ajratadi (super/sub/italic)."""
    segments: List[Tuple[str, dict]] = []
    pos = 0

    def flush_plain(chunk: str) -> None:
        if not chunk:
            return
        # yakka harfli o'zgaruvchilar kursiv (E = m x): so'z ichidagilar tegilmaydi
        parts = _VAR_RE.split(chunk)
        for i, part in enumerate(parts):
            if not part:
                continue
            if i % 2 == 1:
                segments.append((part, {"font": MATH_FONT, "italic": True}))
            else:
                segments.append((part, {"font": BODY_FONT}))

    while pos < len(text):
        m_sup = _SUP_RE.match(text, pos)
        m_sub = _SUB_RE.match(text, pos)
        if m_sup:
            body = m_sup.group(2) if m_sup.group(2) is not None else m_sup.group(3)
            flush_plain("")
            segments.append((body, {"font": MATH_FONT, "sup": True}))
            pos = m_sup.end()
        elif m_sub:
            body = m_sub.group(2) if m_sub.group(2) is not None else m_sub.group(3)
            flush_plain("")
            segments.append((body, {"font": MATH_FONT, "sub": True}))
            pos = m_sub.end()
        else:
            # keyingi markerlargacha oddiy matn
            nxt = len(text)
            for rx in (_SUP_RE, _SUB_RE):
                m = rx.search(text, pos)
                if m:
                    nxt = min(nxt, m.start())
            flush_plain(text[pos:nxt])
            pos = nxt
    return segments


def parse_rich(text: str) -> List[Tuple[str, dict]]:
    """Matnni format segmentlariga ajratadi: [(matn, {font,bold,italic,sup,sub})].

    Tartib muhim: avval `kod` ajratiladi (ichidagi * _ ^ tegilmaydi),
    keyin qolganiga Unicode-matematika + **qalin** + formula qo'llanadi.
    Uchala writer (docx/xlsx/pptx) shu funksiyaga tayanadi.
    """
    segments: List[Tuple[str, dict]] = []
    for i, part in enumerate(_CODE_RE.split(text or "")):
        if not part:
            continue
        if i % 2 == 1:
            segments.append((part, {"font": MONO_FONT, "mono": True}))
            continue
        part = to_unicode_math(part)
        for j, sub in enumerate(_BOLD_RE.split(part)):
            if not sub:
                continue
            if j % 2 == 1:
                segments.append((sub, {"font": BODY_FONT, "bold": True}))
            else:
                segments.extend(_formula_segments(sub))
    return segments


def add_rich_paragraph(paragraph, text: str, size_pt: int = 11) -> None:
    """python-docx paragrafga formula-ongli runlar qo'shadi."""
    _add_runs(paragraph, parse_rich(text), size_pt)


def to_cell_rich_text(text: str, size_pt: int = 11):
    """openpyxl CellRichText: Excel katagida formatlangan formula."""
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    blocks = []
    for chunk, style in parse_rich(text):
        if not chunk:
            continue
        if style.get("mono"):
            font = InlineFont(rFont="Consolas", sz=size_pt)
        else:
            vert = None
            if style.get("sup"):
                vert = "superscript"
            elif style.get("sub"):
                vert = "subscript"
            font = InlineFont(
                rFont=style.get("font", BODY_FONT),
                sz=size_pt,
                b=style.get("bold", False),
                i=style.get("italic", False),
                vertAlign=vert,
            )
        blocks.append(TextBlock(font, chunk))
    if not blocks:
        return ""
    if len(blocks) == 1 and blocks[0].font.rFont in (None, BODY_FONT):
        return chunk  # oddiy matn — format shart emas
    return CellRichText(blocks)


def add_pptx_runs(paragraph, text: str, size_pt: int = 18) -> None:
    """python-pptx paragrafga formula runlari (super/sub = baseline siljish)."""
    from pptx.util import Pt

    for chunk, style in parse_rich(text):
        if not chunk:
            continue
        run = paragraph.add_run()
        run.text = chunk
        run.font.size = Pt(size_pt)
        run.font.bold = style.get("bold", False)
        run.font.italic = style.get("italic", False)
        run.font.name = "Consolas" if style.get("mono") else style.get("font", BODY_FONT)
        if style.get("sup"):
            run._r.get_or_add_rPr().set("baseline", "30000")
        elif style.get("sub"):
            run._r.get_or_add_rPr().set("baseline", "-25000")
