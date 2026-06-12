"""Report rendering: markdown -> PDF (fpdf2) saved under storage/processed/reports."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import text

from ...config import get_settings
from ...db import db_conn

TEAL = (15, 118, 110)
SLATE = (15, 23, 42)
GRAY = (100, 116, 139)


def save_report(building_id: str, report_type: str, title: str,
                markdown: str, agent_run_id: str | None = None,
                summary: dict | None = None) -> dict:
    """Render markdown to PDF, store both files, insert reports row."""
    s = get_settings()
    reports_dir = s.storage_path / "processed" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{report_type}_{stamp}"
    md_path = reports_dir / f"{base}.md"
    pdf_path = reports_dir / f"{base}.pdf"
    md_path.write_text(markdown, encoding="utf-8")
    _markdown_to_pdf(title, markdown, pdf_path)

    report_id = uuid.uuid4()
    import json
    with db_conn() as conn:
        conn.execute(text("""
            INSERT INTO reports (id, building_id, agent_run_id, report_type, title,
                                 status, markdown_path, pdf_path, summary_json)
            VALUES (:id, :b, :run, :rt, :title, 'completed', :md, :pdf,
                    cast(:summary as jsonb))
        """), {"id": report_id, "b": building_id, "run": agent_run_id,
               "rt": report_type, "title": title,
               "md": md_path.relative_to(s.storage_path).as_posix(),
               "pdf": pdf_path.relative_to(s.storage_path).as_posix(),
               "summary": json.dumps(summary or {})})
    return {"report_id": str(report_id), "pdf_path": f"/storage/{pdf_path.relative_to(s.storage_path).as_posix()}",
            "markdown_path": f"/storage/{md_path.relative_to(s.storage_path).as_posix()}"}


class _ReportPDF(FPDF):
    def __init__(self, title: str):
        super().__init__()
        self.report_title = title
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEAL)
        self.cell(0, 6, "GreenFlow", align="L")
        self.set_text_color(*GRAY)
        self.cell(0, 6, self.report_title[:80], align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.line(10, self.get_y() + 1, 200, self.get_y() + 1)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 8, f"GreenFlow - simulation-first building operations - page "
                        f"{self.page_no()}", align="C")


def _latin(s: str) -> str:
    """fpdf2 core fonts are latin-1; degrade gracefully."""
    return s.encode("latin-1", "replace").decode("latin-1")


def _markdown_to_pdf(title: str, markdown: str, out_path: Path) -> None:
    pdf = _ReportPDF(title)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*SLATE)
    pdf.multi_cell(0, 9, _latin(title))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 6, datetime.now().strftime("Generated %Y-%m-%d %H:%M"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    table_buffer: list[list[str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            table_buffer.append(cells)
            continue
        if table_buffer:
            _emit_table(pdf, table_buffer)
            table_buffer = []
        _emit_line(pdf, line)
    if table_buffer:
        _emit_table(pdf, table_buffer)
    pdf.output(str(out_path))


def _emit_line(pdf: FPDF, line: str) -> None:
    stripped = line.strip()
    if not stripped:
        pdf.ln(2)
        return
    if stripped.startswith("# "):
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*SLATE)
        pdf.ln(2)
        pdf.multi_cell(0, 8, _latin(stripped[2:]))
    elif stripped.startswith("## "):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*TEAL)
        pdf.ln(2)
        pdf.multi_cell(0, 7, _latin(stripped[3:]))
    elif stripped.startswith("### "):
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*SLATE)
        pdf.multi_cell(0, 6, _latin(stripped[4:]))
    elif stripped.startswith(("- ", "* ")):
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*SLATE)
        pdf.set_x(14)
        pdf.multi_cell(0, 5.5, _latin("- " + _strip_md(stripped[2:])))
    else:
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*SLATE)
        pdf.multi_cell(0, 5.5, _latin(_strip_md(stripped)))


def _emit_table(pdf: FPDF, rows: list[list[str]]) -> None:
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    width = 190 / ncols
    pdf.ln(1)
    for i, row in enumerate(rows):
        pdf.set_font("Helvetica", "B" if i == 0 else "", 8.5)
        if i == 0:
            pdf.set_fill_color(240, 253, 250)
            pdf.set_text_color(*TEAL)
        else:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(*SLATE)
        for c in range(ncols):
            cell = _strip_md(row[c]) if c < len(row) else ""
            pdf.cell(width, 6, _latin(cell[:38]), border=1, fill=(i == 0))
        pdf.ln(6)
    pdf.ln(2)


def _strip_md(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", re.sub(r"`(.+?)`", r"\1", s))
