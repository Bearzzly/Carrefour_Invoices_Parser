#pip install pdfplumber

# Un fichier
#python invoice_to_csv.py "/chemin/vers/7-4988-1455_facture.pdf" -o sorties.csv

# Un dossier (parcourt récursivement tous les .pdf)
#python invoice_parser.py "/chemin/vers/dossier_factures" -o sorties.csv


import os
import re
import csv
from datetime import datetime
from typing import List, Tuple, Optional

try:
    import pdfplumber
except Exception as e:
    raise SystemExit("This script requires 'pdfplumber'. Install it with: pip install pdfplumber") from e

PRICE_KG_RE = re.compile(
    r"""^\s*(?P<weight>\d+(?:[.,]\d+)?)\s*kg\s*x\s*(?P<price>\d+(?:[.,]\d+)?)\s*€\s*/\s*kg\s*$""",
    re.IGNORECASE
)

# Exemple : "5.5% CHISTORRA REFLETS 1 x 4.70 4.70"
PRODUCT_RE = re.compile(
    r"""^\s*(?:(?:\d{1,2}(?:[.,]\d)?|[0-9]{1,2})\s*%|\d{1,2}\.\d{1,2}\s*%)?\s*(?P<name>.+?)\s+(?P<qty>\d+)\s*x\s*(?P<unit>\d+(?:[.,]\d{1,2})?)\s+(?P<amount>-?\d+(?:[.,]\d{1,2})?)\s*$""",
    re.IGNORECASE
)

# Lignes à ignorer
SKIP_PREFIXES = (
    "remise immédiate",
    "total",
    "taux tva",
    "détails de vos avantages",
    "avantages -10%",
    "ma carte",
    "€ crédités",
    "vignettes",
    "payé par",
    "tva produit",
    "carte bancaire",
)

# Recherche de date
DATE_RES = [
    re.compile(r"(?P<d>\d{2})/(?P<m>\d{2})/(?P<y>\d{4})\s*(?:à\s*)?(?P<h>\d{1,2})[h:](?P<min>\d{2})"),
    re.compile(r"(?P<d>\d{2})[.](?P<m>\d{2})[.](?P<y>\d{2,4})\s+(?P<h>\d{1,2})[:](?P<min>\d{2})"),
]

def normalize_decimal(s: str) -> str:
    return s.replace(",", ".")

def find_date(all_text: str) -> Optional[str]:
    for rx in DATE_RES:
        m = rx.search(all_text)
        if m:
            d, mth, y = int(m.group("d")), int(m.group("m")), int(m.group("y"))
            if y < 100:  # '25' -> 2025
                y += 2000
            h, minute = int(m.group("h")), int(m.group("min"))
            dt = datetime(y, mth, d, h, minute)
            return dt.strftime("%d/%m/%Y")
    return None

def parse_lines_to_rows(lines: List[str], invoice_date: Optional[str]) -> List[Tuple[str, str, str, str, str, str]]:
    """
    Retourne des lignes (name, type, price-kg, QTE x P.U, amount, date).
    Si une ligne 'prix/kg' est trouvée, elle est associée au produit suivant.
    """
    out = []
    pending_pricekg: List[str] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Détecte les prix/kg
        mkg = PRICE_KG_RE.match(line)
        if mkg:
            weight = normalize_decimal(mkg.group("weight"))
            price = normalize_decimal(mkg.group("price"))
            pricekg_str = f"{weight}kg x {price}€/kg"
            pending_pricekg.append(pricekg_str)
            continue

        # Ignore les lignes inutiles
        line_lower = line.lower()
        if any(line_lower.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue

        # Détecte les produits
        mp = PRODUCT_RE.match(line)
        if mp:
            name = mp.group("name").strip()
            name = re.sub(r"^\s*\d{1,2}(?:[.,]\d{1,2})?\s*%\s*", "", name).strip()
            name = re.sub(r"\s{2,}", " ", name)

            qty = mp.group("qty")
            unit = normalize_decimal(mp.group("unit"))
            amount = normalize_decimal(mp.group("amount"))

            qte_pu = f"{qty} x {unit}"
            pricekg = pending_pricekg.pop(0) if pending_pricekg else ""

            if name.lower().startswith("remise"):
                continue

            out.append((name, "", pricekg, qte_pu, amount, invoice_date or ""))
            continue

    return out

def extract_pdf_to_rows(pdf_path: str) -> List[Tuple[str, str, str, str, str, str]]:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = []
        for page in pdf.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            page_texts.append(txt)
        all_text = "\n".join(page_texts)

    inv_date = find_date(all_text)
    lines = all_text.split("\n")
    return parse_lines_to_rows(lines, inv_date)

def extract_invoices_to_csv(input_path: str, output_csv: str) -> None:
    paths: List[str] = []

    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for fn in files:
                if fn.lower().endswith(".pdf"):
                    paths.append(os.path.join(root, fn))
    elif os.path.isfile(input_path) and input_path.lower().endswith(".pdf"):
        paths.append(input_path)
    else:
        raise SystemExit("Provide a PDF file or a directory containing PDFs.")

    rows: List[Tuple[str, str, str, str, str, str]] = []
    for p in sorted(paths):
        try:
            rows.extend(extract_pdf_to_rows(p))
        except Exception as e:
            print(f"[WARN] Failed to parse {p}: {e}")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "type", "price-kg", "QTE x P.U", "amount", "date"])
        writer.writerows(rows)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Extract invoice lines from PDF(s) to CSV.")
    ap.add_argument("input", help="Path to a PDF file or a directory of PDFs")
    ap.add_argument("-o", "--output", default="invoices.csv", help="Output CSV path (default: invoices.csv)")
    args = ap.parse_args()
    extract_invoices_to_csv(args.input, args.output)
