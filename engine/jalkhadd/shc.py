"""Read Soil Health Card PDFs (Hindi 'SHC2025' layout) into farm rows.

Needs `pdftotext` (poppler) for PDFs. Farmer names, phone numbers, GPS and test IDs are deliberately NOT read.
Values are copied as printed; the printed 'श्रेणी' (range) under each value is the medium band, not the value's class,
so no class is taken from the card. Validated on 10 cards of one village only: check new layouts before trusting.
"""

from __future__ import annotations

import re
import shutil
import subprocess

FIELDS = {
    "N": r"उपलब्ध नाइट्रोजन \(N\)\s+([\d.]+)",
    "P": r"उपलब्ध फास्फोरस \(P\)\s+([\d.]+)",
    "K": r"उपलब्ध पोटेशियम \(K\)\s+([\d.]+)",
    "OC": r"कार्बनिक कार्बन \(OC\)\s+([\d.]+)",
    "pH": r"पीएच \(pH\)\s+([\d.]+)",
    "EC": r"([\d.]+)\s*dS/m",
    "S": r"उपलब्ध सल्फर \(S\)\s+([\d.]+)",
    "Zn": r"उपलब्ध जिंक \(Zn\)\s+([\d.]+)",
    "B": r"उपलब्ध बोरॉन \(B\)\s+([\d.]+)",
    "area_ha": r"क्षेत्र:\s*([\d.]+)\s*हेक्टेयर",
    "survey_no": r"सर्वेक्षण संख्या\s*:\s*(\S+)",
}


def parse_text(text: str) -> dict:
    row = {}
    for k, rx in FIELDS.items():
        m = re.search(rx, text)
        row[k] = m.group(1) if m else ""
    m = re.search(r"नमूना एकत्रीकरण दिनांक\s*:\s*(.+?)\s{2,}", text)
    row["sample_date"] = m.group(1).strip() if m else ""
    m = re.search(r"([A-Za-z][A-Za-z ,]+, Haridwar, Uttarakhand)", text)
    row["location"] = m.group(1).strip() if m else ""
    missing = [k for k in ("N", "P", "K", "area_ha") if not row[k]]
    if missing:
        raise ValueError(f"could not find {missing} (different card layout?)")
    return row


def parse_pdf(path: str) -> dict:
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext (poppler) is required to read PDFs; install poppler-utils, or enter the values in a CSV.")
    text = subprocess.run([exe, "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    return parse_text(text)
