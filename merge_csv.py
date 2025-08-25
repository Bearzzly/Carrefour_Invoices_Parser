#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import glob
import csv
import argparse
from typing import List, Tuple, Dict

def _read_csv_dicts(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Lit un CSV en dicts, avec fallback d'encodage.
    Retourne (header, rows).
    """
    last_err = None
    for enc in ("utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or []
                rows = [row for row in reader]
            return header, rows
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err or RuntimeError(f"Impossible de lire le fichier: {path}")

def merge_csv_folder(
    folder_path: str,
    output_csv: str = "merged.csv",
    pattern: str = "*.csv",
    dedupe: bool = False,
    sort_by: str = None,
) -> str:
    """
    Fusionne tous les CSV d'un dossier en un seul CSV.

    - Respecte l'ordre des colonnes du premier fichier trouvé.
    - Vérifie que l'ensemble des colonnes est identique pour tous les fichiers.
    - Optionnel: déduplication des lignes et tri par colonne.

    Retourne le chemin absolu du CSV de sortie.
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Dossier introuvable: {folder_path}")

    paths = sorted(glob.glob(os.path.join(folder_path, pattern)))
    if not paths:
        raise FileNotFoundError(f"Aucun fichier ne correspond à '{pattern}' dans {folder_path}")

    first_header: List[str] = []
    merged_rows: List[List[str]] = []
    total_files = 0
    total_rows = 0

    for p in paths:
        header, rows_dicts = _read_csv_dicts(p)
        if not header:
            # CSV vide ou sans header
            continue

        if not first_header:
            first_header = list(header)
        else:
            if set(header) != set(first_header):
                raise ValueError(
                    f"Les colonnes de '{os.path.basename(p)}' diffèrent de celles du premier fichier.\n"
                    f"Trouvé: {header}\nAttendu: {first_header}"
                )

        # Réordonner chaque ligne selon first_header
        for rd in rows_dicts:
            merged_rows.append([rd.get(col, "") for col in first_header])

        total_files += 1
        total_rows += len(rows_dicts)

    # Déduplication (préserve l'ordre)
    if dedupe:
        seen = set()
        unique_rows = []
        for row in merged_rows:
            t = tuple(row)
            if t not in seen:
                seen.add(t)
                unique_rows.append(row)
        merged_rows = unique_rows

    # Tri
    if sort_by:
        if sort_by not in first_header:
            raise KeyError(f"La colonne '{sort_by}' n'existe pas dans les données: {first_header}")
        idx = first_header.index(sort_by)
        merged_rows.sort(key=lambda r: r[idx])

    # Ecriture
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)) or ".", exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(first_header)
        writer.writerows(merged_rows)

    return os.path.abspath(output_csv)

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fusionner tous les CSV d'un dossier (mêmes colonnes) en un seul CSV."
    )
    ap.add_argument("folder", help="Dossier contenant les fichiers .csv")
    ap.add_argument("output", help="Chemin du CSV de sortie (ex: merged.csv)")
    ap.add_argument("--pattern", default="*.csv", help="Motif des fichiers (par défaut: *.csv)")
    ap.add_argument("--dedupe", action="store_true", help="Supprimer les doublons exacts")
    ap.add_argument("--sort-by", default=None, help="Trier par cette colonne")
    args = ap.parse_args()

    try:
        out = merge_csv_folder(
            folder_path=args.folder,
            output_csv=args.output,
            pattern=args.pattern,
            dedupe=args.dedupe,
            sort_by=args.sort_by,
        )
        print(f"✅ Fusion terminée -> {out}")
        return 0
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
