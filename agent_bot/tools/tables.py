"""Haqiqiy jadvallar: Markdown pipe-jadval -> Word Table / Telegram aligned <pre>.

Notatsiya (prompt shartnomasi):
    | Ustun1 | Ustun2 |
    |--------|--------|
    | a      | b      |

Qoidalar: kataklar qisqa (mobil sig'ishi uchun), '|' katak ichida ishlatilmaydi.
Telegram Bot API'da jadval tegi YO'Q — eng yaqin haqiqiy ko'rinish:
ustun kengligi tekislangan monospace blok. Word'da esa haqiqiy
tahrirlanadigan Table (sarlavha rangi + chegaralar bilan).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Union

_SEP_CELL_RE = re.compile(r"^:?-{1,}:?$")


def _split_row(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_sep_row(cells: List[str]) -> bool:
    return bool(cells) and all(_SEP_CELL_RE.match(c) for c in cells)


@dataclass
class MdTable:
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

    def normalized(self) -> "MdTable":
        width = max([len(self.headers)] + [len(r) for r in self.rows] + [1])
        headers = (self.headers + [""] * width)[:width]
        rows = [(r + [""] * width)[:width] for r in self.rows]
        return MdTable(headers=headers, rows=rows)


def parse_markdown_tables(text: str) -> List[MdTable]:
    """Matndagi barcha pipe-jadvallarni ajratib oladi."""
    tables: List[MdTable] = []
    buf: List[str] = []

    def flush() -> None:
        if len(buf) < 2:
            buf.clear()
            return
        rows = [_split_row(ln) for ln in buf]
        rows = [r for r in rows if not _is_sep_row(r)]
        if rows:
            tables.append(MdTable(headers=rows[0], rows=rows[1:]).normalized())
        buf.clear()

    for ln in (text or "").split("\n"):
        if "|" in ln:
            buf.append(ln)
        else:
            flush()
    flush()
    return tables


def split_blocks(text: str) -> List[Tuple[str, Union[str, MdTable]]]:
    """Matnni ('text', parcha) / ('table', MdTable) bloklarga bo'ladi (docx uchun)."""
    blocks: List[Tuple[str, Union[str, MdTable]]] = []
    buf: List[str] = []

    def flush_text() -> None:
        if buf:
            blocks.append(("text", "\n".join(buf)))
            buf.clear()

    # Qator-qator yig'ish (separator qatorli pipe-blok = jadval)
    cur: List[str] = []
    for ln in (text or "").split("\n"):
        if "|" in ln:
            cur.append(ln)
        else:
            if len(cur) >= 2:
                rows = [_split_row(x) for x in cur]
                rows = [r for r in rows if not _is_sep_row(r)]
                if rows:
                    flush_text()
                    blocks.append(("table", MdTable(headers=rows[0], rows=rows[1:]).normalized()))
                else:
                    buf.extend(cur)
                cur = []
                buf.append(ln)  # jadvaldan keyingi matn tushib qolmasligi uchun
            else:
                buf.extend(cur)
                cur = []
                buf.append(ln)
    if len(cur) >= 2:
        rows = [_split_row(x) for x in cur]
        rows = [r for r in rows if not _is_sep_row(r)]
        if rows:
            flush_text()
            blocks.append(("table", MdTable(headers=rows[0], rows=rows[1:]).normalized()))
        else:
            buf.extend(cur)
    else:
        buf.extend(cur)
    flush_text()
    return blocks


def align_pre(table: MdTable, max_col: int = 18) -> str:
    """Telegram <pre> uchun ustunlari tekislangan monospace jadval."""
    t = table.normalized()
    widths = []
    for i in range(len(t.headers)):
        w = max([len(t.headers[i])] + [len(r[i]) for r in t.rows])
        widths.append(min(w, max_col))

    def fmt_row(cells: List[str]) -> str:
        parts = []
        for cell, w in zip(cells, widths):
            c = cell if len(cell) <= w else cell[: max(w - 1, 1)] + "…"
            parts.append(c.ljust(w))
        return "| " + " | ".join(parts) + " |"

    sep = "|-" + "-|-".join("-" * w for w in widths) + "-|"
    lines = [fmt_row(t.headers), sep] + [fmt_row(r) for r in t.rows]
    out = "\n".join(lines)
    if len(out) > 3500:  # haddan tashqari katta jadvalni kesish
        out = out[:3500].rsplit("\n", 1)[0] + "\n| … |"
    return out


def add_word_table(doc, table: MdTable, font_size: int = 10):
    """python-docx hujjatga haqiqiy tahrirlanadigan jadval qo'shadi."""
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    t = table.normalized()
    grid = doc.add_table(rows=1 + len(t.rows), cols=len(t.headers))
    grid.style = "Table Grid"
    grid.autofit = True

    def shade(cell, fill: str) -> None:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)

    for j, h in enumerate(t.headers):
        cell = grid.cell(0, j)
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.font.size = Pt(font_size)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        shade(cell, "1F497D")
    for i, row in enumerate(t.rows, start=1):
        for j, val in enumerate(row):
            cell = grid.cell(i, j)
            cell.text = ""
            run = cell.paragraphs[0].add_run(val)
            run.font.size = Pt(font_size)
    doc.add_paragraph()  # jadvaldan keyin bo'sh joy
    return grid
