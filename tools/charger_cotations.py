"""Charge les series capturees dans la base des cotations.

Cette base s'accumule : contrairement a reference.db, elle n'est pas effacee a
chaque execution. Le chargement est donc idempotent -- une valeur deja presente
pour un couple (support, date) est remplacee, jamais dupliquee.

La source est pour l'instant le dossier de captures. Le collecteur, plus tard,
alimentera la meme base par le meme chemin.

    python tools/charger_cotations.py
"""
import datetime
import glob
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from collecte import yahoo

RACINE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
HISTORIQUES = os.path.join(RACINE, "data/raw/captures/historiques")
COTATIONS = os.path.join(RACINE, "data/cotations.db")
SCHEMA = os.path.join(RACINE, "db/schema_cotations.sql")


def meilleures_series():
    """La serie la plus fournie par support, avec sa devise et sa provenance."""
    retenues = {}
    for chemin in sorted(glob.glob(os.path.join(HISTORIQUES, "*__yahoo*.json"))):
        fichier = os.path.basename(chemin)
        isin, sonde = fichier.split("__")[0], fichier.split("__")[1].removesuffix(".json")
        charge = open(chemin, encoding="utf-8").read()
        valeurs = yahoo.serie(charge)
        if len(valeurs) > len(retenues.get(isin, {}).get("valeurs", {})):
            retenues[isin] = {"valeurs": valeurs, "sonde": sonde,
                              "devise": yahoo.metadonnees(charge).get("currency")}
    return retenues


def main():
    os.makedirs(os.path.dirname(COTATIONS), exist_ok=True)
    cx = sqlite3.connect(COTATIONS)
    cx.executescript(open(SCHEMA, encoding="utf-8").read())
    maintenant = datetime.datetime.now().isoformat(timespec="seconds")

    total = 0
    print(f"{'ISIN':14s}{'points':>8s}{'devise':>8s}  période                  source")
    for isin, lu in sorted(meilleures_series().items()):
        valeurs, dates = lu["valeurs"], sorted(lu["valeurs"])
        statut = "obtenu" if len(valeurs) >= 100 else ("vide" if not valeurs else "insuffisant")
        if valeurs:
            cx.executemany(
                "INSERT INTO valeur_liquidative (isin, date, valeur, devise, source)"
                " VALUES (?,?,?,?,?) ON CONFLICT (isin, date) DO UPDATE SET"
                " valeur = excluded.valeur, devise = excluded.devise, source = excluded.source",
                [(isin, d.isoformat(), valeurs[d], lu["devise"], lu["sonde"]) for d in dates])
            total += len(valeurs)
        cx.execute("INSERT INTO collecte (isin, source, symbole, tente_le, statut, points,"
                   " debut, fin, devise, detail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (isin, lu["sonde"], None, maintenant, statut, len(valeurs),
                    dates[0].isoformat() if dates else None,
                    dates[-1].isoformat() if dates else None, lu["devise"],
                    "chargé depuis les captures"))
        print(f"{isin:14s}{len(valeurs):>8d}{str(lu['devise']):>8s}  "
              f"{dates[0] if dates else '—'} → {dates[-1] if dates else '—'}  {lu['sonde']}")
    cx.commit()

    supports = cx.execute("SELECT COUNT(DISTINCT isin) FROM valeur_liquidative").fetchone()[0]
    lignes = cx.execute("SELECT COUNT(*) FROM valeur_liquidative").fetchone()[0]
    print(f"\nBase : {os.path.relpath(COTATIONS, RACINE)} "
          f"({os.path.getsize(COTATIONS) / 1024:.0f} Ko)")
    print(f"  {lignes} valeurs sur {supports} supports  (+{total} écrites ce tour)")
    cx.close()


if __name__ == "__main__":
    main()
