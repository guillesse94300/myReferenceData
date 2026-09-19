"""Importe la liste de supports detenus vers les favoris de l'application.

Le fichier source, `data/raw/favorites.txt`, est tenu a la main : colonnes
Fonds, ISIN et « Detenu dans », separees par des tabulations. Seuls les
supports dont l'ISIN existe dans l'univers sont repris ; les autres sont
enumeres, car un fonds absent est une information en soi -- il n'est
accessible dans aucun des deux contrats.

Usage : python tools/importer_favoris.py
"""
import csv
import datetime
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import favoris as suivi

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE = os.path.join(RACINE, "data/raw/favorites.txt")
BASE = os.path.join(RACINE, "data/reference.db")
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def main():
    cx = sqlite3.connect(BASE)
    univers = {r[0]: r[1] for r in cx.execute("SELECT isin, nom FROM instrument")}
    cx.close()

    suivis = suivi.charger()
    aujourdhui = datetime.date.today().isoformat()
    repris, hors_univers, sans_isin = [], [], []
    with open(SOURCE, encoding="utf-8", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter="\t"):
            code = (ligne.get("ISIN") or "").strip()
            libelle = (ligne.get("Fonds") or "").strip()
            if not ISIN.match(code):
                sans_isin.append(libelle)
            elif code not in univers:
                hors_univers.append((code, libelle))
            else:
                suivis[code] = {"ajoute_le": suivis.get(code, {}).get("ajoute_le", aujourdhui),
                                "note": (ligne.get("Détenu dans") or "").strip()}
                repris.append((code, univers[code]))
    suivi.enregistrer(suivis)

    print(f"{len(repris)} support(s) repris dans les favoris :")
    for code, nom in repris:
        print(f"  {code}  {nom}")
    if hors_univers:
        print(f"\n{len(hors_univers)} absent(s) de l'univers, non repris :")
        for code, libelle in hors_univers:
            print(f"  {code}  {libelle}")
    if sans_isin:
        print(f"\n{len(sans_isin)} sans ISIN exploitable :")
        for libelle in sans_isin:
            print(f"  {libelle}")
    print(f"\nListe écrite dans {os.path.relpath(suivi.FICHIER, RACINE)} : {len(suivis)} support(s).")


if __name__ == "__main__":
    main()
