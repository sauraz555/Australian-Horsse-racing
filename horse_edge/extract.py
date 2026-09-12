"""Turn a form guide file (PDF / Excel / CSV / text) into plain text so the agent
can read it. The agent does the understanding; this only extracts characters.
"""
from __future__ import annotations

import csv
import os


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _pdf(path)
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _xlsx(path)
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            return "\n".join(" | ".join(row) for row in csv.reader(f))
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("PDF extraction needs pdfplumber:  pip install pdfplumber")
    out = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            out.append(f"--- page {i} ---")
            out.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                for row in table:
                    out.append(" | ".join("" if c is None else str(c) for c in row))
    return "\n".join(out)


def _xlsx(path: str) -> str:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Excel extraction needs openpyxl:  pip install openpyxl")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"--- sheet {ws.title} ---")
        for row in ws.iter_rows(values_only=True):
            if any(c not in (None, "") for c in row):
                out.append(" | ".join("" if c is None else str(c) for c in row))
    return "\n".join(out)
