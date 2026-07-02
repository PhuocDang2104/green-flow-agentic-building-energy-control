"""Report rendering: markdown -> PDF (fpdf2) saved under storage/processed/reports."""

from __future__ import annotations

import json
import math
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
LIGHT_GRAY = (226, 232, 240)
MUTED = (148, 163, 184)
PALE_TEAL = (232, 246, 244)
PALE_AMBER = (255, 248, 235)
AMBER = (180, 83, 9)


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

    # Upload to MinIO (object storage). pdf_path/markdown_path in DB store the
    # OBJECT KEY (reports/<base>.pdf); the reports router serves them via
    # /media/<key>. Fall back to the legacy /storage relative path if MinIO is
    # unreachable so report generation never hard-fails.
    md_key = f"reports/{base}.md"
    pdf_key = f"reports/{base}.pdf"
    try:
        from ...storage import objectstore
        objectstore.put_file(md_key, md_path, "text/markdown")
        objectstore.put_file(pdf_key, pdf_path, "application/pdf")
    except Exception as exc:  # noqa: BLE001 — object store down -> dùng /storage
        print(f"report upload to object storage failed ({exc}); using /storage")
        md_key = md_path.relative_to(s.storage_path).as_posix()
        pdf_key = pdf_path.relative_to(s.storage_path).as_posix()

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
               "md": md_key, "pdf": pdf_key,
               "summary": json.dumps(summary or {})})
    return {"report_id": str(report_id),
            "pdf_path": _media_url(pdf_key), "markdown_path": _media_url(md_key)}


def _media_url(key: str) -> str:
    """Object key -> URL the frontend can resolve. MinIO keys go through the
    /media proxy; legacy /storage relative paths keep the /storage mount."""
    return f"/media/{key}" if not key.startswith("processed/") else f"/storage/{key}"


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
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 6, datetime.now().strftime("Generated %Y-%m-%d %H:%M"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    table_buffer: list[list[str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("[[gf_chart "):
            if table_buffer:
                _emit_table(pdf, table_buffer)
                table_buffer = []
            _emit_chart_directive(pdf, line)
            continue
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


def _emit_chart_directive(pdf: FPDF, line: str) -> None:
    payload = line.removeprefix("[[gf_chart ").removesuffix("]]").strip()
    try:
        chart = json.loads(payload)
    except json.JSONDecodeError:
        return
    _emit_line_chart(pdf, chart)


def _emit_line_chart(pdf: FPDF, chart: dict) -> None:
    points = [p for p in chart.get("points", []) if p.get("baseline") is not None
              and p.get("optimized") is not None]
    if len(points) < 2:
        return
    if pdf.get_y() + 76 > pdf.h - pdf.b_margin:
        pdf.add_page()

    title = _latin(str(chart.get("title") or "Chart"))
    unit = _latin(str(chart.get("unit") or ""))
    x = pdf.l_margin
    y = pdf.get_y() + 2
    w = pdf.w - pdf.l_margin - pdf.r_margin
    h = 68
    plot_x = x + 10
    plot_y = y + 11
    plot_w = w - 16
    plot_h = h - 25

    vals = [float(p["baseline"]) for p in points] + [float(p["optimized"]) for p in points]
    y_domain = chart.get("y_domain") or []
    domain_min = y_domain[0] if len(y_domain) > 0 else None
    domain_max = y_domain[1] if len(y_domain) > 1 else None
    vmin = float(domain_min) if isinstance(domain_min, (int, float)) else min(vals)
    vmax = float(domain_max) if isinstance(domain_max, (int, float)) else max(vals)
    if abs(vmax - vmin) < 1e-9:
        vmax = vmin + 1
    if not isinstance(domain_min, (int, float)) or not isinstance(domain_max, (int, float)):
        pad = (vmax - vmin) * 0.08
        if not isinstance(domain_min, (int, float)):
            vmin -= pad
        if not isinstance(domain_max, (int, float)):
            vmax += pad
    if chart.get("min_zero"):
        vmin = max(0.0, vmin)

    def sx(idx: int) -> float:
        return plot_x + (plot_w * idx / max(len(points) - 1, 1))

    def sy(value: float) -> float:
        return plot_y + plot_h - ((value - vmin) / (vmax - vmin) * plot_h)

    pdf.set_draw_color(*LIGHT_GRAY)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, w, h, "D")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*SLATE)
    pdf.set_xy(x + 3, y + 2)
    pdf.cell(w - 6, 5, title, new_x="LMARGIN", new_y="NEXT")

    for i in range(4):
        gy = plot_y + plot_h * i / 3
        pdf.set_draw_color(241, 245, 249)
        pdf.line(plot_x, gy, plot_x + plot_w, gy)

    el_nino_from = str(chart.get("el_nino_from") or "")
    if el_nino_from:
        start_idx = _first_point_on_or_after(points, el_nino_from)
        if start_idx is not None:
            band_x = sx(start_idx)
            pdf.set_fill_color(*PALE_AMBER)
            pdf.set_draw_color(253, 211, 77)
            pdf.rect(band_x, plot_y, plot_x + plot_w - band_x, plot_h, "DF")
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(*AMBER)
            pdf.set_xy(plot_x + plot_w - 18, plot_y + 1)
            pdf.cell(16, 3, "El Nino", align="R")

    band = chart.get("band") or {}
    if band.get("y1") is not None and band.get("y2") is not None:
        by1 = sy(float(band["y1"]))
        by2 = sy(float(band["y2"]))
        top, bottom = min(by1, by2), max(by1, by2)
        pdf.set_fill_color(229, 250, 247)
        pdf.set_draw_color(204, 251, 241)
        pdf.rect(plot_x, top, plot_w, bottom - top, "DF")
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*TEAL)
        pdf.set_xy(plot_x + 2, top + 1)
        pdf.cell(30, 3, _latin(str(band.get("label") or "")))

    for threshold in chart.get("thresholds") or []:
        ty = sy(float(threshold))
        pdf.set_draw_color(245, 158, 11)
        _draw_dashed_line(pdf, plot_x, ty, plot_x + plot_w, ty, dash_len=1.8, gap_len=1.2)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*AMBER)
        pdf.set_xy(plot_x + plot_w - 10, ty - 2.5)
        pdf.cell(9, 3, f"{threshold:g}%")

    _draw_area_under_series(pdf, points, "optimized", sx, sy, plot_y + plot_h)

    def draw_series(key: str, color: tuple[int, int, int], dashed: bool = False) -> None:
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.40 if dashed else 0.58)
        prev: tuple[float, float] | None = None
        for idx, point in enumerate(points):
            current = (sx(idx), sy(float(point[key])))
            if prev:
                if dashed:
                    _draw_dashed_line(pdf, prev[0], prev[1], current[0], current[1],
                                      dash_len=1.6, gap_len=1.2)
                else:
                    pdf.line(prev[0], prev[1], current[0], current[1])
            prev = current
        pdf.set_line_width(0.2)

    draw_series("optimized", TEAL)
    draw_series("baseline", GRAY, dashed=True)

    pdf.set_font("Helvetica", "", 7.2)
    legend_y = y + 2.8
    pdf.set_draw_color(*GRAY)
    _draw_dashed_line(pdf, x + w - 72, legend_y + 1.7, x + w - 61, legend_y + 1.7,
                      dash_len=2.0, gap_len=1.0)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(x + w - 59, y + 2)
    pdf.cell(29, 4, "Without AI")
    pdf.set_draw_color(*TEAL)
    pdf.set_line_width(0.55)
    pdf.line(x + w - 29, legend_y + 1.7, x + w - 18, legend_y + 1.7)
    pdf.set_line_width(0.2)
    pdf.set_text_color(*TEAL)
    pdf.set_xy(x + w - 16, y + 2)
    pdf.cell(14, 4, "With AI")
    pdf.set_text_color(*GRAY)
    pdf.set_xy(x + 3, y + 7)
    pdf.cell(0, 4, _axis_label(vmax, unit))
    pdf.set_xy(x + 3, y + h - 16)
    pdf.cell(0, 4, _axis_label(vmin, unit))

    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_text_color(*MUTED)
    for idx in _date_tick_indexes(points):
        label = _latin(str(points[idx].get("label", "")))
        tx = sx(idx)
        pdf.set_xy(tx - 4, y + h - 8)
        pdf.cell(12, 3.5, label, align="C")
    pdf.set_y(y + h + 2)


def _draw_area_under_series(pdf: FPDF, points: list[dict], key: str, sx, sy,
                            bottom_y: float) -> None:
    """Approximate the web chart area fill without creating huge PDF polygons."""
    stride = max(1, len(points) // 260)
    pdf.set_draw_color(*PALE_TEAL)
    pdf.set_line_width(0.15)
    for idx in range(0, len(points), stride):
        px = sx(idx)
        py = sy(float(points[idx][key]))
        pdf.line(px, py, px, bottom_y)
    pdf.set_line_width(0.2)


def _axis_label(value: float, unit: str) -> str:
    if abs(value) >= 1000:
        text = f"{value:,.0f}"
    elif abs(value) >= 100:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.1f}".rstrip("0").rstrip(".")
    return _latin(f"{text} {unit}".strip())


def _date_key(point: dict) -> str:
    raw = str(point.get("x") or point.get("label") or "")
    return raw.split("T", 1)[0]


def _first_point_on_or_after(points: list[dict], date_value: str) -> int | None:
    for idx, point in enumerate(points):
        if _date_key(point) >= date_value:
            return idx
    return None


def _date_tick_indexes(points: list[dict]) -> list[int]:
    first_by_date: list[int] = []
    prev = None
    for idx, point in enumerate(points):
        key = _date_key(point)
        if key != prev:
            first_by_date.append(idx)
            prev = key
    if len(first_by_date) <= 9:
        return first_by_date
    stride = max(1, len(first_by_date) // 8)
    selected = first_by_date[::stride]
    if first_by_date[-1] not in selected:
        selected.append(first_by_date[-1])
    return selected[:10]


def _draw_dashed_line(pdf: FPDF, x1: float, y1: float, x2: float, y2: float,
                      dash_len: float = 3.0, gap_len: float = 1.5) -> None:
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 0:
        return
    ux = dx / dist
    uy = dy / dist
    pos = 0.0
    while pos < dist:
        end = min(pos + dash_len, dist)
        pdf.line(x1 + ux * pos, y1 + uy * pos, x1 + ux * end, y1 + uy * end)
        pos = end + gap_len


def _emit_table(pdf: FPDF, rows: list[list[str]]) -> None:
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    widths = _table_widths(rows, ncols)
    pdf.ln(1)
    for i, row in enumerate(rows):
        pdf.set_font("Helvetica", "B" if i == 0 else "", 8.5)
        if i == 0:
            pdf.set_fill_color(240, 253, 250)
            pdf.set_text_color(*TEAL)
        else:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(*SLATE)
        _emit_table_row(pdf, row, widths, is_header=(i == 0))
    pdf.ln(2)


def _table_widths(rows: list[list[str]], ncols: int) -> list[float]:
    """Column widths tuned for report tables in portrait A4.

    fpdf cells do not wrap by default. These widths reserve more space for
    narrative/evidence columns and less for numeric columns.
    """
    header = [(_strip_md(c) if c else "").strip().lower() for c in rows[0]]
    presets: dict[tuple[str, ...], list[float]] = {
        ("dimension", "score", "target", "status", "backend evidence"): [36, 17, 17, 22, 98],
        ("priority", "severity", "finding", "evidence", "recommended action"): [16, 20, 34, 58, 62],
        ("workstream", "action", "owner", "target window"): [37, 74, 35, 44],
        ("zone", "type", "area m2", "occupancy", "temp c", "load kw", "comfort"): [48, 30, 18, 22, 18, 20, 34],
        ("metric", "current value", "why it matters"): [42, 38, 110],
        ("data domain", "coverage / issue", "interpretation"): [42, 42, 106],
    }
    widths = presets.get(tuple(header[:ncols]))
    if widths:
        return widths
    if ncols == 2:
        return [58, 132]
    if ncols == 3:
        return [46, 48, 96]
    if ncols == 4:
        return [42, 72, 34, 42]
    if ncols == 5:
        return [34, 26, 40, 45, 45]
    return [190 / ncols] * ncols


def _emit_table_row(pdf: FPDF, row: list[str], widths: list[float], is_header: bool) -> None:
    cells = [_strip_md(row[c]) if c < len(row) else "" for c in range(len(widths))]
    line_sets = [_wrap_text(pdf, _latin(cell), width - 2, max_lines=4 if is_header else 5)
                 for cell, width in zip(cells, widths)]
    line_h = 4.2
    row_h = max(7.0, max(len(lines) for lines in line_sets) * line_h + 3.0)
    if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
        pdf.add_page()
    x0, y0 = pdf.get_x(), pdf.get_y()
    for lines, width in zip(line_sets, widths):
        x, y = pdf.get_x(), pdf.get_y()
        pdf.rect(x, y, width, row_h, "DF" if is_header else "D")
        pdf.set_xy(x + 1, y + 1.5)
        for line in lines:
            pdf.cell(width - 2, line_h, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(x + 1)
        pdf.set_xy(x + width, y)
    pdf.set_xy(x0, y0 + row_h)


def _wrap_text(pdf: FPDF, text: str, max_width: float, max_lines: int = 5) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.get_string_width(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = _fit_word(pdf, word, max_width)
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = _fit_word(pdf, lines[-1].rstrip(".") + "...", max_width)
    return lines or [""]


def _fit_word(pdf: FPDF, word: str, max_width: float) -> str:
    if pdf.get_string_width(word) <= max_width:
        return word
    trimmed = word
    while trimmed and pdf.get_string_width(trimmed + "...") > max_width:
        trimmed = trimmed[:-1]
    return (trimmed or word[:1]) + "..."


def _strip_md(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", re.sub(r"`(.+?)`", r"\1", s))
